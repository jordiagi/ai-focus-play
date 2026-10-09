# Video-only accuracy proposal

Date: 2026-10-09. Requested by Jordi; implementation authorized. Compute constraint for this session: local only, no remote GPU.

## Outcome

Train and evaluate using labeled Veo matches; analyze each new Marc or Eric BCC recording without event labels, official match sheets, Veo calibration, or reference period timings guiding that recording. Development audit labels can assess saved predictions without entering inference.

## Baseline evidence

Reproduced on 2026-10-09 using `scripts/local/tune_cv_parity.py --lomo`: four Veo matches, possession MAE 8.82 percentage points at radius 3.4m; leave-one-match-out MAE 10.03 points; pass-share MAE 7.38 points; shots MAE 4.38 per team. Pass totals are derived, not measured (45.62 MAE is not an accuracy headline). This is a historical artifact benchmark, not proof of raw-video-only generalization.

Player observation median gaps: Skyline 7.90s, Fairfax 8.30s, Baltimore 10.68s, NCFC 8.84s. Marc artifacts are similarly sparse. Generalized geometry uses a fixed image trapezoid despite camera movement. Possession associates the ball with a nearest player; nearest-player changes become passes. Full totals are rescaled assuming 40% in-play duration and 11.5 passes/minute. The historical runner can use reference period boundaries, Veo calibration, and official acta reconciliation.

## Implementation order

1. **Inference/evaluation boundary.** Add explicit video-only mode, isolate reference inputs, prevent shared fallback artifacts, identify every source and model version. Save predictions before scoring. Reject legacy artifact manifests lacking video-only provenance.
2. **Input inventory and local pilot.** Register Veo, Marc, and BCC sources separately from scorer registry; measure real timestamps, sampling gaps, source availability, and camera setup. Prepare short local clips at 10–15fps; do not run expensive full-match experiments first.
3. **Tracking and geometry.** Trial synchronized dense player/ball detection, camera-motion-aware tracking, automatic pitch-line/keypoint calibration, and explicit geometry confidence. Compare existing calibration implementations before writing another solver. Do not project airborne balls onto turf and claim recovered 3D coordinates. Maintain team A/B until names can be reliably mapped; abstain rather than use pitch-half fallback.
4. **Temporal events.** Train from timestamped Veo events with difficult negatives. Possession/passes require control → release → transit → reception. Detect shots using temporal visual context as well as trajectory evidence. Separate goals from generic attempts and goal confirmations from inferred kickoff offsets.
5. **Unlabeled adaptation.** Use development Marc/BCC recordings for consistency learning and cautious teacher/student pseudo-labeling after the supervised baseline clears gates. Do not pseudo-label locked test games into training or treat pseudo-labels as ground truth.
6. **Accuracy and coverage.** Score precision/recall, one-to-one timestamp matching, team attribution, calibration/tracking quality, and observable-play coverage. Remove extrapolated totals from measured results. Keep unknown/off-screen/dead-ball states explicit.

## Dataset and evaluation contract

- Split by entire match, additionally holding out venue/camera setup. Adjacent clips remain in the same split.
- Four Veo registry entries currently contain aggregate stats; detailed event timestamps are currently available for Skyline only. Gather other event exports before expecting a well-supported temporal model.
- Treat Veo labels as reference annotations with possible error, not infallible truth. Independently audit disagreements and difficult negatives.
- Keep a small independent audit set from Marc/BCC, unused by inference or adaptation. Without such reference evidence, accuracy on these domains remains unknown.
- Freeze event definitions, timing tolerances, baselines, and proposed gates before tuning. Initial proposed gates: possession MAE ≤5 points on held-out games; completed-pass precision ≥80%; shot precision ≥80% and recall ≥70%. These are targets, not achieved claims; require coverage reporting and per-domain results, and choose a coverage floor from the pilot before training.
- Start with possession/pass control and shots; defer jersey identity and less observable foul/tackle classes until the foundations pass.

## References considered

- SoccerNet game-state reconstruction (calibration, tracking, roles, team and jersey modules): https://github.com/SoccerNet/sn-gamestate
- SoccerNet temporal action spotting: https://www.soccer-net.org/tasks/action-spotting
- Unbiased Teacher, semi-supervised object detection and pseudo-label bias: https://arxiv.org/abs/2102.09480

These are candidate starting points; they do not establish performance on our amateur footage.
