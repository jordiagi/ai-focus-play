#!/usr/bin/env python3
"""Adversarial defect probes. Owned by the orchestrator; never by a package author.

Each probe is designed to catch the *false complete* most likely for that defect --
not merely to confirm the happy path. A probe that cannot run yet reports SKIP with a
reason. It never reports PASS for something it did not actually test.

Usage: python scripts/local/verify.py [d1 d3 ...|all]
Exit: 0 all selected probes PASS, 30 any FAIL, 1 harness error.
"""
import json, os, shutil, signal, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV = os.path.join(REPO, "backend/.venv/bin/python")
LIVE_DB = os.path.join(REPO, "backend/.local/data/veo.db")
PORT = 8099
RESULTS = []


def record(pid, name, status, detail):
    RESULTS.append((pid, name, status, detail))


class Server:
    """A real uvicorn process. Probes that check env-dependent behaviour MUST use
    this: config.py reads os.getenv at import time, so flipping a flag inside an
    already-running pytest process proves nothing.

    isolate=True runs the server against a COPY of the live DB in a temp dir.
    Any probe that issues a write MUST isolate: read-only is currently unenforced,
    so a DELETE probe against the live DB really does delete. (It did, once.)"""

    def __init__(self, env_extra, port=PORT, isolate=True):
        self.tmp = None
        env = {**os.environ, "PYTHONPATH": REPO, **env_extra}
        if isolate:
            self.tmp = tempfile.mkdtemp(prefix="aifp-verify-")
            media = os.path.join(self.tmp, "media")
            os.makedirs(media, exist_ok=True)
            if os.path.exists(LIVE_DB):
                shutil.copy(LIVE_DB, os.path.join(self.tmp, "veo.db"))
            # Carry the SMALL media files across. Without them the server sees an
            # empty media dir, every clip is legitimately omitted, and probes that
            # inspect exported clips pass vacuously by checking nothing.
            src_media = os.path.join(REPO, "backend/.local/media")
            if os.path.isdir(src_media):
                for name in os.listdir(src_media):
                    fp = os.path.join(src_media, name)
                    if os.path.isfile(fp) and os.path.getsize(fp) <= 8 * 1024 * 1024:
                        shutil.copy(fp, os.path.join(media, name))
            env.update({"AIFP_DATA_DIR": self.tmp,
                        "AIFP_DB_PATH": os.path.join(self.tmp, "veo.db"),
                        "AIFP_MEDIA_DIR": os.path.join(self.tmp, "media")})
        self.env = env
        self.port = port
        self.proc = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [VENV, "-m", "uvicorn", "backend.src.app.main:app",
             "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "error"],
            cwd=REPO, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            preexec_fn=os.setsid)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/capabilities", timeout=1)
                return self
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("server died: " + self.proc.stderr.read().decode()[-500:])
                time.sleep(0.2)
        raise RuntimeError("server did not come up")

    def __exit__(self, *a):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
        if self.proc and self.proc.poll() is None:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            try: self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired: os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)

    def req(self, method, path, data=None, ctype=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        r = urllib.request.Request(url, method=method, data=data)
        if ctype: r.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(r, timeout=20) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            return -1, str(e).encode()


def d1_read_only():
    """Catches: guards 'verified' inside pytest where READ_ONLY was already False at
    import; and middleware that blocks unconditionally (equally broken)."""
    drawing = json.dumps({"timestamp": 1, "tool_type": "arrow", "coordinates": []}).encode()
    try:
        with Server({"AIFP_READ_ONLY": "1"}) as s:
            _, body = s.req("GET", "/api/capabilities")
            caps = json.loads(body)
            blocked = {
                "capabilities.allow_uploads": caps.get("allow_uploads") is False,
                "capabilities.read_only": caps.get("read_only") is True,
                "DELETE match": s.req("DELETE", "/api/matches/demo-arlington-skyline")[0] in (401, 403),
                "POST drawings": s.req("POST", "/api/matches/demo-arlington-skyline/drawings",
                                       drawing, "application/json")[0] in (401, 403),
                "GET matches still works": s.req("GET", "/api/matches")[0] == 200,
            }
        # Negative case: with the flag off, the same writes must succeed.
        with Server({"AIFP_READ_ONLY": "0"}) as s:
            code, _ = s.req("POST", "/api/matches/demo-arlington-skyline/drawings",
                            drawing, "application/json")
            blocked["negative: writes allowed when flag off"] = code in (200, 201)
    except Exception as e:
        return "FAIL", f"harness error: {e}"
    bad = [k for k, v in blocked.items() if not v]
    return ("PASS", "all gated, negative case holds") if not bad else ("FAIL", "; ".join(bad))


def d3_index():
    """Catches: 'create_all creates it' -- true on a FRESH db, no-op on the live one.
    Probes a COPY OF THE LIVE DB with the index explicitly dropped."""
    if not os.path.exists(LIVE_DB):
        return "SKIP", "no live db"
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy(LIVE_DB, tmp)
    try:
        c = sqlite3.connect(tmp)
        c.execute("DROP INDEX IF EXISTS ix_radar_match_time"); c.commit(); c.close()
        r = subprocess.run([VENV, "-c",
            "from backend.src.storage.database import init_db; init_db()"],
            cwd=REPO, env={**os.environ, "PYTHONPATH": REPO, "AIFP_DB_PATH": tmp},
            capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return "FAIL", f"init_db failed: {r.stderr.strip()[-200:]}"
        c = sqlite3.connect(tmp)
        plan = " ".join(str(x) for row in c.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM radar_frames WHERE match_id=? "
            "AND timestamp BETWEEN ? AND ? ORDER BY timestamp", ("demo-arlington-skyline", 0, 10)
        ) for x in row)
        c.close()
        if "ix_radar_match_time" in plan:
            return "PASS", "migration creates index on an existing db"
        return "FAIL", f"plan={plan.strip()}"
    finally:
        for suf in ("", "-wal", "-shm"):
            try: os.unlink(tmp + suf)
            except OSError: pass


def d4_fallback_label():
    """Catches: literal flipped to 'demo' everywhere, mislabelling genuine ML runs too."""
    src = os.path.join(REPO, "backend/src/api/routes/matches.py")
    txt = open(src).read()
    hard = 'analysis_mode = "heuristic"' in txt
    return (("FAIL", "matches.py still hardcodes analysis_mode = \"heuristic\" "
                     "unconditionally after a run that may be synthetic fallback")
            if hard else ("PASS", "no unconditional heuristic label"))


def d5_seed_consistency():
    """Catches: the live DB row patched while the seed code still fabricates.
    Seeds a FRESH database and checks the seed's own internal consistency."""
    tmpdir = tempfile.mkdtemp()
    try:
        env = {**os.environ, "PYTHONPATH": REPO,
               "AIFP_DATA_DIR": tmpdir, "AIFP_DB_PATH": os.path.join(tmpdir, "v.db")}
        r = subprocess.run([VENV, "-c",
            "from backend.src.storage.repository import match_repo; print('ok')"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return "FAIL", f"seed failed: {r.stderr.strip()[-200:]}"
        c = sqlite3.connect(os.path.join(tmpdir, "v.db"))
        goals = {}
        for team, in c.execute("SELECT team FROM events WHERE lower(event_type)='goal'"):
            goals[team] = goals.get(team, 0) + 1
        row = c.execute("SELECT data FROM analytics LIMIT 1").fetchone()
        c.close()
        if not row:
            return "FAIL", "no analytics row seeded"
        a = json.loads(row[0])
        hs, aw = a.get("home_stats", {}), a.get("away_stats", {})
        problems = []
        if hs.get("goals") != goals.get("home", 0):
            problems.append(f"analytics home goals={hs.get('goals')} vs {goals.get('home',0)} events")
        if aw.get("goals") != goals.get("away", 0):
            problems.append(f"analytics away goals={aw.get('goals')} vs {goals.get('away',0)} events")
        nshots = len([1 for _ in a.get("shot_map", [])])
        nev = sum(goals.values())
        if nshots and nshots != nev:
            problems.append(f"shot_map={nshots} vs {nev} shot/goal events")
        for f in ("tackles", "passes_completed"):
            if hs.get(f) not in (None, 0):
                problems.append(f"home_stats.{f}={hs.get(f)} is fabricated (never computed)")
        return ("PASS", "seed is internally consistent") if not problems else ("FAIL", "; ".join(problems))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def d7_orphan_sweep():
    """Catches: a grep-based 'pass'. The string 'interrupted' appears in a READ at
    repository.py:430 and in a comment, so searching source is worthless. This plants
    a stale 'running' job in a copy of the DB, brings the repository up, and checks
    whether a recovery sweep actually reclaimed it."""
    if not os.path.exists(LIVE_DB):
        return "SKIP", "no live db"
    tmpdir = tempfile.mkdtemp()
    try:
        db = os.path.join(tmpdir, "veo.db")
        shutil.copy(LIVE_DB, db)
        c = sqlite3.connect(db)
        mid = c.execute("SELECT id FROM matches LIMIT 1").fetchone()
        if not mid:
            return "SKIP", "no match row to attach a probe job to"
        c.execute("INSERT INTO jobs (id, match_id, kind, status, progress, step, "
                  "started_at, attempts) VALUES (?,?,?,?,?,?,?,?)",
                  ("probe-stale", mid[0], "cv_analysis", "running", 0.0,
                   "Initializing analysis...", 0.0, 0))
        c.commit(); c.close()
        r = subprocess.run([VENV, "-c",
            "from backend.src.storage.repository import match_repo; print('up')"],
            cwd=REPO, capture_output=True, text=True, timeout=180,
            env={**os.environ, "PYTHONPATH": REPO, "AIFP_DATA_DIR": tmpdir,
                 "AIFP_DB_PATH": db, "AIFP_MEDIA_DIR": os.path.join(tmpdir, "media")})
        if r.returncode != 0:
            return "FAIL", f"repository failed to start: {r.stderr.strip()[-200:]}"
        c = sqlite3.connect(db)
        st = c.execute("SELECT status FROM jobs WHERE id='probe-stale'").fetchone()
        c.close()
        if st and st[0] == "running":
            return "FAIL", ("a stale 'running' job survived startup; nothing sweeps it "
                            "to 'interrupted', so the job is stuck forever")
        return "PASS", f"stale job reclaimed (status={st[0] if st else 'gone'})"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def d8_saved_outcome():
    """Catches: 'saved' invented for every non-goal attempt. We cannot distinguish
    saved/blocked/missed without GK-contact detection; correct value is 'unknown'."""
    src = open(os.path.join(REPO, "backend/src/services/pipeline/cv_engine.py")).read()
    if '"saved"' in src:
        return "FAIL", 'cv_engine.py still labels non-goal attempts "saved" (fabricated)'
    return "PASS", "no invented shot outcome"


def _team_signature(video, cwd=None):
    """Run the engine on one video in a fresh process; return a hash of team labels."""
    code = (
        "import hashlib,json,sys;"
        "from pathlib import Path;"
        "from backend.src.services.pipeline.cv_engine import cv_engine;"
        "rf,_,_,_ = cv_engine.process_video(Path(sys.argv[1]),'H','A');"
        "sig=[[p.team for p in f.players] for f in rf];"
        "print(hashlib.sha256(json.dumps(sig).encode()).hexdigest()[:16])"
    )
    r = subprocess.run([VENV, "-c", code, video], cwd=cwd or REPO,
                       env={**os.environ, "PYTHONPATH": cwd or REPO},
                       capture_output=True, text=True, timeout=600)
    return r.stdout.strip().splitlines()[-1] if r.returncode == 0 else f"ERR:{r.stderr[-120:]}"


def d2_determinism():
    """Catches: a seed added while state still leaks through the module singleton.
    The decisive probe runs TWO videos in ONE process and compares the second
    against running it alone -- a per-process check cannot see the leak."""
    media = os.path.join(REPO, "backend/.local/media")
    a = os.path.join(media, "demo_match.mp4")
    if not os.path.exists(a):
        return "SKIP", "no demo_match.mp4 to drive the engine"
    tmp = tempfile.mkdtemp()
    try:
        # A second, visually different clip so kit centroids would differ if they leaked.
        b = os.path.join(tmp, "b.mp4")
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "testsrc=size=640x360:rate=5:duration=12", "-pix_fmt", "yuv420p", b],
                           capture_output=True, timeout=180)
        if r.returncode != 0 or not os.path.exists(b):
            return "SKIP", "ffmpeg could not build a second clip"

        # (i) repeatability within one process
        code = (
            "import hashlib,json,sys;"
            "from pathlib import Path;"
            "from backend.src.services.pipeline.cv_engine import cv_engine;"
            "outs=[];"
            "\nfor _ in range(3):\n"
            "    rf,_,_,_ = cv_engine.process_video(Path(sys.argv[1]),'H','A');"
            "    outs.append(hashlib.sha256(json.dumps([[p.team for p in f.players] for f in rf]).encode()).hexdigest()[:16])\n"
            "print(len(set(outs)), outs[0])"
        )
        rr = subprocess.run([VENV, "-c", code, a], cwd=REPO,
                            env={**os.environ, "PYTHONPATH": REPO},
                            capture_output=True, text=True, timeout=900)
        if rr.returncode != 0:
            return "FAIL", f"repeat run failed: {rr.stderr.strip()[-200:]}"
        parts = rr.stdout.strip().splitlines()[-1].split()
        if parts[0] != "1":
            return "FAIL", f"same input gave {parts[0]} different team labellings in one process"

        # (ii) the leak probe: B after A, versus B alone
        code2 = (
            "import hashlib,json,sys;"
            "from pathlib import Path;"
            "from backend.src.services.pipeline.cv_engine import cv_engine;"
            "cv_engine.process_video(Path(sys.argv[1]),'H','A');"
            "rf,_,_,_ = cv_engine.process_video(Path(sys.argv[2]),'H','A');"
            "print(hashlib.sha256(json.dumps([[p.team for p in f.players] for f in rf]).encode()).hexdigest()[:16])"
        )
        r2 = subprocess.run([VENV, "-c", code2, a, b], cwd=REPO,
                            env={**os.environ, "PYTHONPATH": REPO},
                            capture_output=True, text=True, timeout=900)
        if r2.returncode != 0:
            return "FAIL", f"sequential run failed: {r2.stderr.strip()[-200:]}"
        after = r2.stdout.strip().splitlines()[-1]
        alone = _team_signature(b)
        if after != alone:
            return "FAIL", (f"video B labelled differently after A ({after}) than alone "
                            f"({alone}) - per-match state leaks through the singleton")
        return "PASS", f"repeatable in-process and no cross-match leak (sig={alone})"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def d6_zip_streaming():
    """Catches: a missing clip silently replaced by the full match video, and an
    archive built entirely in memory. Compares every zip member byte-for-byte
    against the candidate substitutes."""
    import hashlib, io, zipfile
    media = os.path.join(REPO, "backend/.local/media")
    subs = {}
    for name in ("demo_match.mp4", "match_full_720p.mp4"):
        fp = os.path.join(media, name)
        if os.path.exists(fp):
            h = hashlib.sha256()
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            subs[h.hexdigest()] = name
    if not subs:
        return "SKIP", "no candidate substitute video present to compare against"
    try:
        with Server({"AIFP_READ_ONLY": "0"}) as s:
            code, body = s.req("GET", "/api/matches")
            matches = json.loads(body)
            # Pick a match that actually HAS highlights. Note the live DB accumulates
            # junk matches because the test suite is not isolated from it (defect 9).
            mid = None
            for m in matches:
                c, hb = s.req("GET", f"/api/matches/{m['id']}/highlights")
                if c == 200 and json.loads(hb):
                    mid = m["id"]; break
            if mid is None:
                return "SKIP", "no match with highlights to export"
            code, body = s.req("GET", f"/api/matches/{mid}/highlights/export")
            if code != 200:
                return "FAIL", f"export returned {code} for match {mid}"
    except Exception as e:
        return "FAIL", f"harness error: {e}"
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
    except Exception as e:
        return "FAIL", f"response is not a valid zip: {e}"
    names = [n for n in z.namelist() if not n.lower().endswith((".txt", ".json", ".md"))]
    bad = []
    for n in names:
        h = hashlib.sha256(z.read(n)).hexdigest()
        if h in subs:
            bad.append(f"{n} is byte-identical to {subs[h]}")
    if bad:
        return "FAIL", "; ".join(bad)
    if not names:
        return "FAIL", ("zip contained no clip members at all - nothing was actually "
                        "checked, so this is not evidence of a fix")
    return "PASS", f"{len(names)} clip member(s), all distinct, none a full video"


def d10_no_invented_analytics():
    """Catches: a plausible-looking literal standing in for a statistic nothing computes.

    This is the class of bug that survived the first hardening pass: the seed was fixed
    to an empty series while the PIPELINE kept a hardcoded decay curve, and the UI
    rendered it as a real bar chart. Behavioural, not a grep: it runs the engine and
    inspects what it actually returns."""
    media = os.path.join(REPO, "backend/.local/media")
    clip = os.path.join(media, "demo_match.mp4")
    if not os.path.exists(clip):
        return "SKIP", "no clip to drive the engine"
    code = (
        "import json,sys;"
        "from pathlib import Path;"
        "from backend.src.services.pipeline.cv_engine import cv_engine;"
        "_,_,_,a = cv_engine.process_video(Path(sys.argv[1]),'H','A');"
        "print(json.dumps({"
        "'pass_strings':a.pass_strings,"
        "'heatmaps':a.heatmaps,"
        "'home':{k:getattr(a.home_stats,k) for k in "
        "  ('tackles','passes_completed','corners','fouls','free_kicks','throw_ins',"
        "   'penalties','possession_won')},"
        "'pass_locations':a.pass_locations}))"
    )
    r = subprocess.run([VENV, "-c", code, clip], cwd=REPO,
                       env={**os.environ, "PYTHONPATH": REPO},
                       capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        return "FAIL", f"engine run failed: {r.stderr.strip()[-200:]}"
    try:
        a = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        return "FAIL", f"could not parse engine output: {e}"

    bad = []
    for side, series in (a.get("pass_strings") or {}).items():
        if series:
            bad.append(f"pass_strings[{side}]={series} but nothing detects passes")
    for side, series in (a.get("heatmaps") or {}).items():
        if series:
            bad.append(f"heatmaps[{side}] is populated but nothing computes heatmaps")
    for k, v in (a.get("home") or {}).items():
        if v not in (None,):
            bad.append(f"home_stats.{k}={v} but nothing computes it")
    # A substituted default betrays itself as a suspiciously round number.
    for side, thirds in (a.get("pass_locations") or {}).items():
        vals = [v for v in (thirds or {}).values() if v is not None]
        if vals and sorted(vals) in ([20.0, 20.0, 60.0], [25.0, 25.0, 50.0]):
            bad.append(f"pass_locations[{side}]={thirds} is the hardcoded fallback split")
    return ("PASS", "no invented analytics literal returned") if not bad else ("FAIL", "; ".join(bad))


def d11_ml_ingest_honesty():
    """Catches: the ML ingest claiming a position, a mode or a count it does not have.

    Three separate lies were available here and one of them was live during development:

    * `Event.pitch_x/pitch_y` had a column default of (52.5, 34.0) -- the centre spot --
      and SQLAlchemy applies a scalar default when the value is None at INSERT time. The
      ingest passed None for "no metric calibration exists" and every row came back on
      the centre spot. The model said unknown, the database said centre spot.
    * The seeded demo match is pinned to analysis_mode="demo", so ingesting there would
      leave ML events presented under a demo label.
    * The capability surface is a separate claim from the events, so counts can drift
      from what is actually stored.

    Behavioural, not a grep: it ingests into a throwaway database and inspects the rows
    that come back."""
    art = os.path.join(REPO, "backend/.local/artifacts/mosaic")
    pred = os.path.join(art, "pred_all.json")
    man = os.path.join(art, "manifest_all.json")
    if not (os.path.exists(pred) and os.path.exists(man)):
        return "SKIP", "no ingestable prediction set on disk"
    tmp = tempfile.mkdtemp(prefix="d11-")
    db = os.path.join(tmp, "probe.db")
    env = {**os.environ, "PYTHONPATH": REPO, "AIFP_DB_PATH": db}
    mk = (
        "import sys,time;"
        "from backend.src.storage.repository import MatchRepository;"
        "from backend.src.domain.models.match import Match;"
        "r=MatchRepository();"
        "r.save_match(Match(id='probe-match',title='p',home_team='H',away_team='A',"
        "date='2026-01-01',video_url='/x.mp4',duration_seconds=10.0,created_at=time.time()))"
    )
    r = subprocess.run([VENV, "-c", mk], cwd=REPO, env=env, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        return "FAIL", f"could not create a probe match: {r.stderr.strip()[-200:]}"

    ing = os.path.join(REPO, "backend/src/services/pipeline/ml_ingest.py")
    r = subprocess.run([VENV, ing, "--pred", pred, "--manifest", man,
                        "--match-id", "probe-match"], cwd=REPO, env=env,
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return "FAIL", f"ingest failed or self-verification tripped: {r.stderr.strip()[-300:]}"

    # refusing the pinned demo match is part of the contract
    r2 = subprocess.run([VENV, ing, "--pred", pred, "--manifest", man,
                         "--match-id", "demo-arlington-skyline"], cwd=REPO, env=env,
                        capture_output=True, text=True, timeout=600)
    if r2.returncode == 0:
        return "FAIL", "ingest wrote into the pinned demo match instead of refusing"

    # inspect the rows, not the model that produced them
    con = sqlite3.connect(db)
    try:
        pos = con.execute("select count(*) from events where match_id='probe-match' "
                          "and (pitch_x is not null or pitch_y is not null)").fetchone()[0]
        mode = con.execute("select analysis_mode from matches where id='probe-match'"
                           ).fetchone()[0]
        caps_raw = con.execute("select event_capabilities from matches "
                               "where id='probe-match'").fetchone()[0]
        rows = con.execute("select event_type, count(*) from events "
                           "where match_id='probe-match' group by 1").fetchall()
    finally:
        con.close()
    if pos:
        return "FAIL", (f"{pos} ingested events carry a pitch position though the "
                        f"pipeline has no metric calibration")
    if mode != "ml":
        return "FAIL", f"analysis_mode is {mode!r} after an ML ingest"
    if not caps_raw:
        return "FAIL", "no capability surface was persisted"
    caps = json.loads(caps_raw)
    stored = dict(rows)
    for label, cap in caps.items():
        if cap.get("status") == "detected" and cap.get("count") != stored.get(label, 0):
            return "FAIL", (f"capability {label!r} claims {cap.get('count')} but "
                            f"{stored.get(label, 0)} events are stored")
        if cap.get("status") == "unavailable" and not cap.get("reason"):
            return "FAIL", f"capability {label!r} is unavailable with no reason"
    n = sum(stored.values())
    return "PASS", (f"{n} events ingested, no invented positions, mode=ml, "
                    f"{len(stored)} labels reconcile with stored rows")


PROBES = {
    "d1": ("read-only enforcement", d1_read_only),
    "d2": ("CV determinism", d2_determinism),
    "d3": ("radar index on live db", d3_index),
    "d4": ("honest fallback label", d4_fallback_label),
    "d5": ("seed self-consistency", d5_seed_consistency),
    "d6": ("streaming zip export", d6_zip_streaming),
    "d7": ("orphaned-job sweep", d7_orphan_sweep),
    "d8": ("invented shot outcome", d8_saved_outcome),
    "d10": ("invented analytics literals", d10_no_invented_analytics),
    "d11": ("ml ingest honesty", d11_ml_ingest_honesty),
}

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    sel = list(PROBES) if not args or args == ["all"] else args
    for pid in sel:
        if pid not in PROBES:
            print(f"unknown probe {pid}", file=sys.stderr); return 1
        name, fn = PROBES[pid]
        try:
            st, detail = fn()
        except Exception as e:
            st, detail = "FAIL", f"probe raised: {e}"
        record(pid, name, st, detail)
    w = max(len(n) for _, n, _, _ in RESULTS)
    for pid, name, st, detail in RESULTS:
        print(f"{st:4}  {pid}  {name:<{w}}  {detail}")
    npass = sum(1 for *_, st, _ in [(r[0], r[1], r[2], r[3]) for r in RESULTS] if st == "PASS")
    nfail = sum(1 for r in RESULTS if r[2] == "FAIL")
    nskip = sum(1 for r in RESULTS if r[2] == "SKIP")
    print(f"RESULT: pass={npass} fail={nfail} skip={nskip}")
    return 30 if nfail else 0

if __name__ == "__main__":
    sys.exit(main())
