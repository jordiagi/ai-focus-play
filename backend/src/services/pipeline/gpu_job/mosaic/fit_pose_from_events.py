#!/usr/bin/env python3
"""D-A step 3d — fit the pitch pose from Veo's event coordinates, in AZIMUTH only.

Fitting the pitch to the detected lines failed: the multi-pitch complex supplies lines
from several fields and no rigid model satisfies the mixture. Veo's own events settle
which field is ours and where the ball was, so use them instead of the lines.

The measurement that shapes this. `locate_play_region.py` projected the frame centre at
213 event times into the panorama, and the cloud is a NARROW ELEVATION BAND barely
taller than the centre circle -- the virtual camera pans and zooms but hardly tilts, so
frame-centre elevation is almost constant no matter where the ball is. Frame centre is
therefore useless as a proxy for the ball's ground position in elevation.

In AZIMUTH it is excellent: corr(veo_x, azimuth) = +0.904, rising monotonically across
all ten deciles of pitch length, while corr(veo_z, azimuth) = +0.08. So use the one
component that is actually informative and throw the other away.

Azimuth is scale-invariant, which is exactly why this is safe: it cannot be traded off
against camera height the way the line fit was. The scale comes from the centre circle,
whose radius is known (9.15 m) and which `calibrate_from_circle.py` already fits to a
median of 0.0 px -- and which the event cloud independently confirms is on OUR pitch.

Fitting alpha, beta, gamma, tx, ty, L, W to 171 azimuth observations with h fixed is
heavily overdetermined, and the residual is reported in degrees so it can be read
against the camera's own tracking lag.
"""
import argparse, json, math
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="from locate_play_region.py")
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--circle-calib", required=True,
                    help="from calibrate_from_circle.py; supplies the metric scale h")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fix-h", action="store_true", default=True)
    a = ap.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from calibrate_panorama import normals, basis
    from scipy.optimize import least_squares

    C = json.loads(Path(a.cameras).read_text())
    scale, (x0, y0) = float(C["scale"]), C["origin"]
    cal = json.loads(Path(a.circle_calib).read_text())["params"]
    h = float(cal["camera_height_m"])

    pts = [p for p in json.loads(Path(a.points).read_text()) if p["veo_x"] is not None]
    U = np.array([p["u"] for p in pts])
    xn = np.array([p["veo_x"] for p in pts])
    zn = np.array([p["veo_z"] for p in pts])
    th_obs = (U + x0) / scale

    def wrap(d):
        return (d + math.pi) % (2 * math.pi) - math.pi

    # The ground normal comes from the CIRCLE, not from here. Azimuth is only weakly
    # sensitive to it, and letting it float drove both angles onto their bounds. Each
    # constraint is used where it is strong: the circle for the plane and the scale,
    # the event azimuths for the in-plane pose and the pitch dimensions.
    AL, BE = float(cal["alpha_rad"]), float(cal["beta_rad"])

    def model_az(p):
        ga, tx, ty, L, W = p
        al, be = AL, BE
        n = normals(np.array([al]), np.array([be]))[0]
        e1, e2 = basis(n[None, :])
        e1, e2 = e1[0], e2[0]
        X = (xn - 0.5) * L
        Y = (zn - 0.5) * W
        cg, sg = math.cos(ga), math.sin(ga)
        Xr, Yr = X * cg - Y * sg, X * sg + Y * cg
        P = (-h * n)[None, :] + (Xr + tx)[:, None] * e1[None, :] \
            + (Yr + ty)[:, None] * e2[None, :]
        return np.arctan2(P[:, 0], P[:, 2])

    lo = np.array([0.0, -200., -200., 80., 45.])
    hi = np.array([2 * math.pi, 200., 200., 120., 80.])
    xs = np.array([0.2, 10., 10., 5., 5.])

    best = None
    for ga0 in np.arange(0, 2 * math.pi, math.radians(15)):
        for ty0 in (-80., -50., -30., 30., 50., 80.):
            p0 = np.clip(np.array([ga0, 0.0, ty0, 105., 68.]), lo, hi)
            try:
                s = least_squares(lambda p: wrap(model_az(p) - th_obs), p0,
                                  bounds=(lo, hi), x_scale=xs, loss="soft_l1",
                                  f_scale=math.radians(3.0), max_nfev=3000)
            except Exception:
                continue
            if best is None or s.cost < best.cost:
                best = s
    p = best.x
    res = np.degrees(wrap(model_az(p) - th_obs))
    doc = {
        "job": "D-A step 3d: pose from Veo event azimuths",
        "n_events": len(pts), "camera_height_m_fixed": round(h, 3),
        "params": {"alpha_rad": round(AL, 5), "beta_rad": round(BE, 5),
                   "gamma_rad": round(float(p[0]), 5),
                   "tx_m": round(float(p[1]), 2), "ty_m": round(float(p[2]), 2),
                   "pitch_L_m": round(float(p[3]), 2), "pitch_W_m": round(float(p[4]), 2)},
        "alpha_beta_source": "centre-circle fit (held fixed)",
        "on_bounds": [k for k, lo_, hi_, v in
                      zip(["gamma", "tx", "ty", "L", "W"], lo, hi, p)
                      if abs(v - lo_) < 1e-6 or abs(v - hi_) < 1e-6],
        "azimuth_residual_deg": {
            "median_abs": round(float(np.median(np.abs(res))), 3),
            "mean_abs": round(float(np.abs(res).mean()), 3),
            "p90_abs": round(float(np.percentile(np.abs(res), 90)), 3),
            "rms": round(float(np.sqrt((res ** 2).mean())), 3),
        },
        "baseline_if_pose_were_meaningless_deg": round(
            float(np.degrees(np.std(wrap(th_obs - np.median(th_obs))))), 2),
    }
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
