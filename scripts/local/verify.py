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
            os.makedirs(os.path.join(self.tmp, "media"), exist_ok=True)
            if os.path.exists(LIVE_DB):
                shutil.copy(LIVE_DB, os.path.join(self.tmp, "veo.db"))
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


def d2_determinism():
    return "SKIP", ("needs a committed fixture clip + a run_cv entrypoint; "
                    "probe must run TWO videos in ONE process to catch the "
                    "team_centers leak via the module singleton")


def d6_zip_streaming():
    return "SKIP", ("needs a match with real highlight clips seeded; probe measures "
                    "peak RSS < 200 MB and sha-compares every zip member against the "
                    "full video")


PROBES = {
    "d1": ("read-only enforcement", d1_read_only),
    "d2": ("CV determinism", d2_determinism),
    "d3": ("radar index on live db", d3_index),
    "d4": ("honest fallback label", d4_fallback_label),
    "d5": ("seed self-consistency", d5_seed_consistency),
    "d6": ("streaming zip export", d6_zip_streaming),
    "d7": ("orphaned-job sweep", d7_orphan_sweep),
    "d8": ("invented shot outcome", d8_saved_outcome),
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
