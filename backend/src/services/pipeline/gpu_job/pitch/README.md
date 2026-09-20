# Pitch calibration (G2)

Learned pitch-keypoint calibration via **PnLCalib**, installed on gpu-box at
`/opt/PnLCalib` with weights `SV_kp` / `SV_lines` (GPL-2.0 — fine for local use,
relevant only if this is ever distributed).

## Why not feature matching

Two earlier attempts used generic SIFT features and both failed. On this footage those
features land on trees, tents, parked cars and *adjacent pitches* — all off the pitch
plane, which is the one plane we need. Learned pitch keypoints are on-plane by
construction, and their semantics also disambiguate our second (blue) line system.

## Scripts, in the order they were used

| script | question it answers |
| :-- | :-- |
| `probe_detection.py` | does PnLCalib detect anything on our frames at all? |
| `sweep_thresholds.py` | how does calibration *coverage* vary with threshold? |
| `score_alignment.py` | is a calibration actually RIGHT? projects the pitch model back and scores overlap with real white lines |
| `validate_metric.py` | how many METRES is it wrong by? the L2 gate |

## The lesson worth keeping

`sweep_thresholds.py` reports 85% coverage at 0.10/0.20. `score_alignment.py` shows that
same setting has *worse* median alignment (0.19 vs 0.29) and yields no additional
well-aligned frames. **Coverage is not accuracy.** Use 0.15 / 0.30.

Also: PnLCalib's `inference.py` silently writes the unmodified frame when calibration
fails, so a failure looks like a successful no-op. Always probe numerically.
