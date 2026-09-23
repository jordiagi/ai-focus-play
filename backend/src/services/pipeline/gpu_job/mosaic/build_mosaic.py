#!/usr/bin/env python3
"""D-A step 1 — build ONE consistent mosaic from the homography graph.

Order matters here, and it is the opposite of the obvious one. D-0 measured that
chaining frame-to-frame accumulates a 10.6x drift factor, so the mosaic is NOT built by
walking the video. It is built by globally solving the whole gated graph at once, which
is possible because `measure_loop_closure.py` showed the planar model holds (median
loop-closure 1.14 px, flat in loop span) -- so the drift is an estimation problem with
loop closures available to fix it, not a model failure.

Three stages, each reported separately so a partial result stays legible:

  1. INIT       every frame -> reference by widest-bottleneck path through the graph
                (maximise the weakest edge on the path, not the hop count)
  2. REFINE     sparse bundle adjustment over ALL gated edges simultaneously
  3. RENDER     per-pixel MEDIAN of the warped frames

The residual is reported over **all** gated edges, including the ones no path used, so
it measures global consistency rather than how well the tree fits itself.

Stage 3 uses the median deliberately: a pixel of pitch is stationary across the match
while players move through it, so the median composites away the players and leaves the
line markings. That is exactly the input a pitch-calibration model wants, and it is the
thing no single frame of this footage provides.
"""
import argparse, sys, heapq, json, math
from pathlib import Path


def widest_path(n, edges, ref):
    """Maximin path from ref to every node: maximise the weakest edge (inlier count)
    along the path. A path is only as trustworthy as its worst homography."""
    adj = {i: [] for i in range(n)}
    for e in edges:
        adj[e["i"]].append((e["j"], e["inliers"]))
        adj[e["j"]].append((e["i"], e["inliers"]))
    best = {ref: math.inf}
    prev = {ref: None}
    pq = [(-math.inf, ref)]
    while pq:
        w, u = heapq.heappop(pq)
        w = -w
        if w < best.get(u, -math.inf):
            continue
        for v, iw in adj[u]:
            nw = min(w, iw)
            if nw > best.get(v, -math.inf):
                best[v] = nw
                prev[v] = u
                heapq.heappush(pq, (-nw, v))
    return best, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True, help="graph JSON from measure_loop_closure.py")
    ap.add_argument("--out-image", required=True)
    ap.add_argument("--out", required=True, help="report JSON")
    ap.add_argument("--out-homographies", default=None,
                    help="frame -> mosaic homographies, for propagating to every frame")
    ap.add_argument("--max-canvas", type=int, default=2600)
    ap.add_argument("--max-warp-scale", type=float, default=6.0,
                    help="skip frames whose warp stretches them beyond this (degenerate)")
    ap.add_argument("--render-frames", type=int, default=60)
    ap.add_argument("--strip", type=int, default=256, help="render strip height, bounds RAM")
    ap.add_argument("--no-refine", action="store_true")
    a = ap.parse_args()

    import cv2, numpy as np
    from scipy.optimize import least_squares
    from scipy.sparse import lil_matrix

    G = json.loads(Path(a.graph).read_text())
    times, W, Hh = G["times"], G["width"], G["height"]
    edges = G["edges"]
    n = len(times)
    frames = {int(k): v for k, v in G["frames"].items()}

    # largest connected component only -- a disjoint view cluster cannot share a mosaic
    adj = {i: set() for i in range(n)}
    for e in edges:
        adj[e["i"]].add(e["j"])
        adj[e["j"]].add(e["i"])
    seen, comps = set(), []
    for s in range(n):
        if s in seen:
            continue
        st, comp = [s], []
        seen.add(s)
        while st:
            u = st.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    keep = set(comps[0])
    edges = [e for e in edges if e["i"] in keep and e["j"] in keep]

    # reference = highest-degree frame in the component (best-connected view)
    deg = {i: len(adj[i] & keep) for i in keep}
    ref = max(deg, key=lambda i: deg[i])

    best, prev = widest_path(n, edges, ref)
    Hm = {e["i"] * 10000 + e["j"]: np.array(e["H"]).reshape(3, 3) for e in edges}
    for e in edges:
        Hm[e["j"] * 10000 + e["i"]] = np.linalg.inv(np.array(e["H"]).reshape(3, 3))

    # frame -> ref
    # Walk the widest-path TREE outward from the reference. Sorting by bottleneck
    # width is not enough: a parent and child can tie, and then the child is visited
    # first and silently dropped.
    children = {}
    for v, u in prev.items():
        if u is not None:
            children.setdefault(u, []).append(v)
    Href = {ref: np.eye(3)}
    stack = [ref]
    while stack:
        u = stack.pop()
        for v in children.get(u, ()):
            if v in Href:
                continue
            Href[v] = Href[u] @ Hm[v * 10000 + u]  # v -> u -> ref
            stack.append(v)
    nodes = sorted(Href)
    idx = {v: k for k, v in enumerate(nodes)}

    corners = np.float32([[0, 0], [W, 0], [W, Hh], [0, Hh]]).reshape(-1, 1, 2)

    def residuals_from(Hd):
        out = []
        for e in edges:
            i, j = e["i"], e["j"]
            if i not in Hd or j not in Hd:
                continue
            pred = np.linalg.inv(Hd[j]) @ Hd[i]      # i -> ref -> j
            meas = Hm[i * 10000 + j]
            if abs(pred[2, 2]) < 1e-12:
                continue
            p1 = cv2.perspectiveTransform(corners, pred / pred[2, 2]).reshape(-1, 2)
            p2 = cv2.perspectiveTransform(corners, meas / meas[2, 2]).reshape(-1, 2)
            out.append(float(np.mean(np.linalg.norm(p1 - p2, axis=1))))
        return out

    r_init = residuals_from(Href)

    report = {"job": "D-A step 1: global mosaic",
               "command": " ".join(sys.argv), "frames_total": n,
              "component_frames": len(keep), "edges_used": len(edges),
              "reference_frame_index": ref, "reference_time_s": times[ref],
              "reference_degree": deg[ref],
              "placed_frames": len(nodes),
              "edge_residual_px_init": summarise(r_init)}

    # ---- stage 2: sparse bundle adjustment over every gated edge ----
    if not a.no_refine and len(nodes) > 2:
        free = [v for v in nodes if v != ref]
        fidx = {v: k for k, v in enumerate(free)}

        def pack(Hd):
            return np.concatenate([(Hd[v] / Hd[v][2, 2]).ravel()[:8] for v in free])

        def unpack(x):
            Hd = {ref: np.eye(3)}
            for v in free:
                Hd[v] = np.append(x[fidx[v] * 8:fidx[v] * 8 + 8], 1.0).reshape(3, 3)
            return Hd

        use = [e for e in edges if e["i"] in idx and e["j"] in idx]

        # Vectorised residual. A per-edge Python loop here would make finite-difference
        # jacobians over ~1400 parameters unusable, so every edge is evaluated as one
        # batched matrix op and the measured corners are precomputed once.
        I = np.array([e["i"] for e in use])
        J = np.array([e["j"] for e in use])
        Wt = np.sqrt(np.minimum([e["inliers"] for e in use], 1000) / 100.0)[:, None, None]
        ch = np.hstack([corners.reshape(-1, 2), np.ones((4, 1))]).T        # 3x4
        Meas = np.stack([Hm[e["i"] * 10000 + e["j"]] for e in use])
        mp = Meas @ ch
        P2 = mp[:, :2] / mp[:, 2:3]

        slot = {v: k for k, v in enumerate(free)}
        slot[ref] = len(free)

        def build(x):
            Hs = np.empty((len(free) + 1, 3, 3))
            Hs[:len(free)] = np.concatenate(
                [x.reshape(len(free), 8), np.ones((len(free), 1))], axis=1
            ).reshape(len(free), 3, 3)
            Hs[len(free)] = np.eye(3)
            return Hs

        Islot = np.array([slot[e["i"]] for e in use])
        Jslot = np.array([slot[e["j"]] for e in use])

        def fun(x):
            Hs = build(x)
            Hi, Hj = Hs[Islot], Hs[Jslot]
            try:
                pred = np.linalg.inv(Hj) @ Hi
            except np.linalg.LinAlgError:
                return np.full(len(use) * 8, 1e3)
            q = pred @ ch
            w = q[:, 2:3]
            bad = np.abs(w) < 1e-9
            w = np.where(bad, 1e-9, w)
            P1 = q[:, :2] / w
            d = (P1 - P2) * Wt
            d = np.where(np.isfinite(d), d, 1e3)
            return d.reshape(len(use), 8).ravel()

        S = lil_matrix((len(use) * 8, len(free) * 8), dtype=int)
        for k, e in enumerate(use):
            for v in (e["i"], e["j"]):
                if v in fidx:
                    S[k * 8:(k + 1) * 8, fidx[v] * 8:fidx[v] * 8 + 8] = 1

        sol = least_squares(fun, pack(Href), jac_sparsity=S.tocsr(),
                            method="trf", loss="huber", f_scale=3.0,
                            max_nfev=60, verbose=0)
        Href = unpack(sol.x)
        report["bundle_adjustment"] = {
            "free_frames": len(free), "edges": len(use),
            "nfev": int(sol.nfev), "status": int(sol.status)}
        report["edge_residual_px_final"] = summarise(residuals_from(Href))
    else:
        report["edge_residual_px_final"] = report["edge_residual_px_init"]

    # ---- stage 3: render ----
    quads = {}
    for v in nodes:
        p = cv2.perspectiveTransform(corners, Href[v] / Href[v][2, 2]).reshape(-1, 2)
        area = 0.5 * abs(sum(p[i][0] * p[(i + 1) % 4][1] - p[(i + 1) % 4][0] * p[i][1]
                             for i in range(4)))
        if math.sqrt(max(area, 1) / (W * Hh)) <= a.max_warp_scale and np.isfinite(p).all():
            quads[v] = p
    allp = np.concatenate(list(quads.values()))
    x0, y0 = allp[:, 0].min(), allp[:, 1].min()
    x1, y1 = allp[:, 0].max(), allp[:, 1].max()
    sc = min(1.0, a.max_canvas / max(x1 - x0, y1 - y0))
    Cw, Ch = int((x1 - x0) * sc) + 1, int((y1 - y0) * sc) + 1
    T = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc], [0, 0, 1]])

    sel = sorted(quads)
    if len(sel) > a.render_frames:
        step = len(sel) / a.render_frames
        sel = [sel[int(k * step)] for k in range(a.render_frames)]

    warped, masks = [], []
    for v in sel:
        img = cv2.imread(frames[v])
        M = T @ (Href[v] / Href[v][2, 2])
        w_ = cv2.warpPerspective(img, M, (Cw, Ch), flags=cv2.INTER_LINEAR)
        m_ = cv2.warpPerspective(np.full((Hh, W), 255, np.uint8), M, (Cw, Ch),
                                 flags=cv2.INTER_NEAREST)
        warped.append(w_)
        masks.append(m_)

    out = np.zeros((Ch, Cw, 3), np.uint8)
    cov = np.zeros((Ch, Cw), np.uint16)
    for y in range(0, Ch, a.strip):
        y2 = min(Ch, y + a.strip)
        stack = np.stack([w[y:y2] for w in warped])
        mk = np.stack([m[y:y2] > 0 for m in masks])
        cov[y:y2] = mk.sum(axis=0)
        s = stack.astype(np.float32)
        s[~mk] = np.nan
        with np.errstate(all="ignore"):
            med = np.nanmedian(s, axis=0)
        out[y:y2] = np.nan_to_num(med).astype(np.uint8)

    Path(a.out_image).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(a.out_image, out)
    report["mosaic"] = {
        "path": a.out_image, "width": Cw, "height": Ch, "scale": round(float(sc), 4),
        "frames_rendered": len(sel), "frames_placed": len(quads),
        "frames_dropped_degenerate": len(nodes) - len(quads),
        "coverage_frac": round(float((cov > 0).mean()), 3),
        "median_stack_depth": int(np.median(cov[cov > 0])) if (cov > 0).any() else 0,
    }
    if a.out_homographies:
        Path(a.out_homographies).write_text(json.dumps({
            "reference_time_s": times[ref], "canvas": [Cw, Ch],
            "T": T.tolist(),
            "frames": {str(times[v]): (T @ (Href[v] / Href[v][2, 2])).tolist()
                       for v in nodes}}))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


def summarise(v):
    if not v:
        return None
    import statistics as st
    s = sorted(v)
    return {"n": len(s), "median": round(st.median(s), 2),
            "p90": round(s[int(0.9 * len(s))], 2), "max": round(s[-1], 2)}


if __name__ == "__main__":
    raise SystemExit(main())
