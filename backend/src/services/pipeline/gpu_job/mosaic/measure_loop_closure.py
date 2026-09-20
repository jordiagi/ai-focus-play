#!/usr/bin/env python3
"""D-A step 0 — is a globally consistent mosaic even POSSIBLE on this footage?

D-A assumes the physical Veo camera is fixed and the export is a virtual pan/zoom crop
of one panorama. If that holds, every frame relates to every other by a homography and
a single consistent mosaic reference frame exists. If Veo's panorama has parallax (a
multi-camera rig stitched per-frame) or a varying projection, it does not, and D-A
fails at the root no matter how good the stitching code is.

The existing 0.31-3.93 px figure does NOT test this. That was a round trip A->B->A,
where H_BA is fitted as the inverse of the same correspondences -- it is self-consistent
by construction and cannot detect an inconsistent model.

**A closed loop over three or more distinct frames can.** Compose A->B->C->A: for a true
planar homography the result is the identity, and any deviation is model error that no
amount of global optimisation will remove. That is the measurement here.

Reported as the mean corner displacement in pixels after going round the loop:

  < ~5 px    the model holds; a consistent mosaic exists and drift is only an
             estimation problem, fixable by global optimisation over loop closures
  ~5-20 px   marginal; a mosaic exists but will be soft
  > ~20 px   the planar model is wrong; D-A's premise fails

Only edges at or above the measured reliability gate (>=100 RANSAC inliers) are used --
an ungated homography is garbage (36-52 px round trip) and would fake a failure here.

Also reports graph connectivity, which decides whether one mosaic can cover the whole
match or whether it fragments into disjoint view clusters.
"""
import argparse, itertools, json, math, random, subprocess, statistics as st
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

_G = {}


def grab(video, t, out, width):
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "2",
                        str(out)], check=True)
    return out


def _init(paths, nfeatures):
    """Each worker computes its own SIFT features once. Recomputing is cheaper than
    pickling ~190 MB of descriptors to every process."""
    import cv2
    sift = cv2.SIFT_create(nfeatures=nfeatures)
    _G["f"] = {}
    for k, p in paths.items():
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        kp, des = sift.detectAndCompute(img, None)
        _G["f"][k] = (kp, des, img.shape)
    _G["bf"] = cv2.BFMatcher()


def _pair(job):
    import cv2, numpy as np
    i, j = job
    ka, da, shape = _G["f"][i]
    kb, db, _ = _G["f"][j]
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return i, j, 0, None
    knn = _G["bf"].knnMatch(da, db, k=2)
    good = [m for m, n in (p for p in knn if len(p) == 2)
            if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return i, j, 0, None
    src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None or mask is None:
        return i, j, 0, None
    return i, j, int(mask.sum()), [float(x) for x in H.ravel()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--t0", type=float, default=562.0)
    ap.add_argument("--t1", type=float, default=6132.0)
    ap.add_argument("--step", type=float, default=30.0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--nfeatures", type=int, default=2000)
    ap.add_argument("--min-inliers", type=int, default=100)
    ap.add_argument("--max-loops", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--graph-out", default=None,
                    help="persist the gated homography graph for the mosaic builder")
    a = ap.parse_args()

    import numpy as np

    times = [round(a.t0 + i * a.step, 3)
             for i in range(int((a.t1 - a.t0) / a.step) + 1)]
    paths = {i: str(grab(Path(a.video), t, Path(a.frames_dir) / f"{int(t*1000):08d}.jpg",
                         a.width)) for i, t in enumerate(times)}
    n = len(times)

    jobs = list(itertools.combinations(range(n), 2))
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init,
                             initargs=(paths, a.nfeatures)) as ex:
        res = list(ex.map(_pair, jobs, chunksize=64))

    H = {}
    deg = [0] * n
    for i, j, inl, h in res:
        if inl >= a.min_inliers and h is not None:
            M = np.array(h).reshape(3, 3)
            H[(i, j)] = M
            try:
                H[(j, i)] = np.linalg.inv(M)
            except np.linalg.LinAlgError:
                del H[(i, j)]
                continue
            deg[i] += 1
            deg[j] += 1

    # connectivity over the gated graph
    adj = {i: set() for i in range(n)}
    for (i, j) in H:
        adj[i].add(j)
    seen, comps = set(), []
    for s in range(n):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        comps.append(sorted(comp))
    comps.sort(key=len, reverse=True)

    # triangles, sampled
    tri = [(i, j, k) for i, j, k in itertools.combinations(range(n), 3)
           if (i, j) in H and (j, k) in H and (i, k) in H]
    random.Random(a.seed).shuffle(tri)
    tri = tri[:a.max_loops]

    w = h_ = None
    import cv2
    img = cv2.imread(paths[0], cv2.IMREAD_GRAYSCALE)
    h_, w = img.shape
    corners = np.float32([[0, 0], [w, 0], [w, h_], [0, h_]]).reshape(-1, 1, 2)

    errs, sep = [], []
    for i, j, k in tri:
        L = H[(k, i)] @ H[(j, k)] @ H[(i, j)]   # A -> B -> C -> A
        if abs(L[2, 2]) < 1e-12:
            continue
        L = L / L[2, 2]
        p = cv2.perspectiveTransform(corners, L).reshape(-1, 2)
        e = float(np.mean(np.linalg.norm(p - corners.reshape(-1, 2), axis=1)))
        if math.isfinite(e):
            errs.append(e)
            sep.append(max(times[i], times[j], times[k]) - min(times[i], times[j], times[k]))

    errs_s = sorted(errs)
    def pct(q):
        return round(errs_s[min(len(errs_s) - 1, int(q * len(errs_s)))], 2) if errs_s else None

    # does closure error grow with how far apart the loop's frames are?
    band = {}
    for e, s in zip(errs, sep):
        b = int(s // 300) * 300
        band.setdefault(b, []).append(e)
    band_stats = {str(k): {"loops": len(v), "median_px": round(st.median(v), 2)}
                  for k, v in sorted(band.items())}

    med = st.median(errs) if errs else None
    doc = {
        "job": "D-A step 0: loop-closure consistency of the planar model",
        "frames": n, "span_s": [a.t0, a.t1], "step_s": a.step,
        "width": a.width, "min_inliers_gate": a.min_inliers,
        "pairs_tested": len(jobs), "edges_gated": len(H) // 2,
        "edge_density": round((len(H) // 2) / len(jobs), 4),
        "degree": {"median": st.median(deg), "min": min(deg), "max": max(deg),
                   "isolated_frames": sum(1 for d in deg if d == 0)},
        "components": {"count": len(comps),
                       "sizes": [len(c) for c in comps[:10]],
                       "largest_frac": round(len(comps[0]) / n, 3) if comps else None},
        "triangles_available": len([1 for i, j, k in itertools.combinations(range(n), 3)
                                    if (i, j) in H and (j, k) in H and (i, k) in H]),
        "loops_scored": len(errs),
        "closure_px": {"median": round(med, 2) if med else None,
                       "p10": pct(0.10), "p25": pct(0.25), "p75": pct(0.75),
                       "p90": pct(0.90), "max": round(max(errs), 2) if errs else None},
        "closure_by_loop_span": band_stats,
        "verdict": (None if med is None else
                    "MODEL HOLDS" if med < 5 else
                    "MARGINAL" if med < 20 else "PLANAR MODEL FAILS"),
    }
    if a.graph_out:
        Path(a.graph_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.graph_out).write_text(json.dumps({
            "times": times, "width": w, "height": h_,
            "min_inliers_gate": a.min_inliers,
            "frames": {str(i): paths[i] for i in range(n)},
            "edges": [{"i": i, "j": j, "inliers": inl, "H": h}
                      for i, j, inl, h in res
                      if inl >= a.min_inliers and h is not None],
        }))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
