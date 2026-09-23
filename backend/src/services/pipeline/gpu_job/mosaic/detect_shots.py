#!/usr/bin/env python3
"""P1: goal-end motion, fitted on period 1, then evaluated once on period 2.

No Veo coordinates or team labels are used. The score uses the unchanged benchmark
matcher. End anchors are inherited from period-1 restart predictions: goal_xi,
with goal-kick xi supplying an end where no goal_xi was observed. These are camera
coordinates, not metric goal lines. All proximity/motion cutoffs are fitted.
"""
import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys

import numpy as np

# Import the existing scorer without creating an unowned __pycache__ artifact.
sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[6]
TYPE = "FootballShot"


def read_period(path, bounds):
    # JSON is a single list: deserialize, immediately partition, never compute
    # features, statistics or normalisations on the held-out portion during fit.
    return sorted((p for p in json.loads(Path(path).read_text())
                   if bounds[0] <= p['t'] <= bounds[1]), key=lambda p: p['t'])


def references(path, period):
    with open(path) as f:
        return sorted(({'video_s': int(r['video_time_ms']) / 1000}
                       for r in csv.DictReader(f)
                       if int(r['period_id']) == period and r['event_type'] == TYPE),
                      key=lambda r: r['video_s'])


def motion(track, frame, ends, gap):
    t = np.array([p['t'] for p in track])
    u = np.array([p['u'] for p in track])
    xi = (u - frame['u_lo']) / (frame['u_hi'] - frame['u_lo'])
    dt = np.diff(t)
    dx = np.diff(xi)
    # Choose the closer inherited goal-end anchor, without predicting a team.
    anchors = np.array(ends)
    goal = anchors[np.argmin(abs(xi[:-1, None] - anchors), axis=1)]
    distance = abs(xi[:-1] - goal)
    toward = dx * np.sign(goal - xi[:-1]) / np.maximum(dt, 1e-9)
    valid = (dt > 0) & (dt <= gap) & (toward > 0)
    return t[:-1][valid], toward[valid], distance[valid]


def candidates(features, distance, separation):
    times, speed, dist = features
    eligible = np.flatnonzero(dist <= distance)
    order = sorted(eligible, key=lambda i: (-speed[i], times[i]))
    picked = []
    for i in order:
        if all(abs(times[i] - times[j]) >= separation for j in picked):
            picked.append(i)
    return [(round(float(times[i]), 2), float(speed[i])) for i in picked]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for arg in ('track', 'candidates', 'frame', 'restart-pred', 'pred', 'manifest', 'out'):
        ap.add_argument('--' + arg, required=True)
    ap.add_argument('--bench', default=str(REPO / 'benchmarks/raw/veo_events_447.csv'))
    ap.add_argument('--fps', type=float, default=5.0)
    ap.add_argument('--budgets', type=float, nargs='+', default=[1., 1.5, 2., 3.])
    ap.add_argument('--budget-tolerance', type=float, default=.05)
    ap.add_argument('--p1', type=float, nargs=2, default=[562.3, 2879.3])
    ap.add_argument('--p2', type=float, nargs=2, default=[3674.4, 6132.1])
    a = ap.parse_args()
    if a.fps <= 0 or not 0 <= a.budget_tolerance < 1 or min(a.budgets) <= 0:
        ap.error('fps/budgets must be positive; budget-tolerance must be in [0,1)')
    for bounds in (a.p1, a.p2):
        if bounds[0] >= bounds[1]:
            ap.error('period bounds must be increasing')
    if a.p1[1] >= a.p2[0]:
        ap.error('periods must be disjoint and chronological')
    spec = importlib.util.spec_from_file_location('shot_benchmark', REPO / 'scripts/local/score-benchmark.py')
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    benchmark = json.loads((REPO / 'benchmarks/veo_reference.json').read_text())
    tol = benchmark['events']['per_type'][TYPE]['match_tolerance_s']

    def block(times, refs):
        tp, _ = scorer.match_one_type(refs, [{'video_s': t} for t in times], tol)
        precision, recall, f1 = scorer.f1(tp, len(times) - tp, len(refs) - tp)
        return dict(n_pred=len(times), n_ref=len(refs), tp=tp,
                    precision=precision, recall=recall, f1=f1)

    frame = json.loads(Path(a.frame).read_text())
    restarts = [e for e in json.loads(Path(a.restart_pred).read_text())['events']
                if e.get('period') == 1]
    # 0.5 is the already validated restart detector's defend-end split, not a
    # newly assumed pitch boundary. Reuse its classification without re-fitting.
    ends = []
    for low in (True, False):
        values = [e['goal_xi'] for e in restarts
                  if 'goal_xi' in e and (e['goal_xi'] < .5) == low]
        if not values:
            values = [e['xi'] for e in restarts if e['event_type'] == 'FootballGoalKick'
                      and (e['xi'] < .5) == low]
        if not values:
            raise ValueError('period-1 restart predictions do not cover both ends')
        ends.append(float(np.median(values)))
    ref1 = references(a.bench, 1)
    track1 = read_period(a.track, a.p1)
    # Sweep feature configurations and the speed threshold on period 1 only.
    # Quantiles specify search points, not assumed geometric pitch boundaries.
    caps = [None] + sorted(set(a.budgets))
    best = {k: None for k in caps}
    cells = 0
    for gap_frames in (2, 4, 6):
        gap = gap_frames / a.fps
        features = motion(track1, frame, ends, gap)
        if not len(features[0]):
            continue
        for quantile, separation in itertools.product((.2, .4, .6, .8), (3., 6., 10.)):
            distance = float(np.quantile(features[2], quantile))
            ranked = candidates(features, distance, separation)
            cells += 1
            # Whole tied-score groups: an inference threshold must emit all ties.
            for n in range(len(ranked) + 1):
                if 0 < n < len(ranked) and ranked[n-1][1] == ranked[n][1]:
                    continue
                threshold = ranked[n-1][1] if n else float(np.nextafter(ranked[0][1], np.inf))
                result = block([t for t, _ in ranked[:n]], ref1)
                config = dict(max_gap_s=gap, end_distance_max=distance,
                              min_sep_s=separation, toward_speed_min=threshold,
                              distance_quantile=quantile, goal_end_xi=ends)
                for k in caps:
                    if k is not None and n > k * len(ref1):
                        continue
                    previous = best[k]
                    if previous is None or (result['f1'], -n) > (previous[0]['f1'], -previous[0]['n_pred']):
                        best[k] = (result, config)
    if best[None] is None:
        raise ValueError('no usable period-1 motion')
    chosen = next((k for k in caps[1:] if best[k][0]['f1'] >=
                   (1 - a.budget_tolerance) * best[None][0]['f1']), None)
    result1, config = best[chosen]
    # Immutable serialization is the freeze boundary. Nothing below fits anything.
    frozen = json.dumps(config, sort_keys=True)
    freeze_hash = hashlib.sha256(frozen.encode()).hexdigest()
    print('FROZEN period1 configuration: ' + frozen, file=sys.stderr, flush=True)

    def predict(track):
        c = json.loads(frozen)
        ranked = candidates(motion(track, frame, c['goal_end_xi'], c['max_gap_s']),
                            c['end_distance_max'], c['min_sep_s'])
        return sorted(t for t, s in ranked if s >= c['toward_speed_min'])

    pred1 = predict(track1)
    assert block(pred1, ref1) == result1
    # The only held-out evaluation: features, predictions, references and controls.
    pred2 = predict(read_period(a.track, a.p2))
    ref2 = references(a.bench, 2)
    result2 = block(pred2, ref2)
    oop = json.loads((Path(a.track).parent / 'pred_oop.json').read_text())['events']
    controls = {}
    for period, times, refs, bounds in ((1, pred1, ref1, a.p1), (2, pred2, ref2, a.p2)):
        rng = np.random.default_rng(11 + period)
        samples = [block(sorted(rng.uniform(*bounds, size=len(times))), refs)['f1']
                   for _ in range(1000)]
        proxy = [e['video_s'] for e in oop if bounds[0] <= e['video_s'] <= bounds[1]]
        controls[str(period)] = dict(chance=dict(trials=1000, n_pred=len(times),
            mean_f1=float(np.mean(samples)), p90_f1=float(np.percentile(samples, 90))),
            oop_proxy=block(proxy, refs))
    chance2 = controls['2']['chance']['mean_f1']
    ratio = result2['f1'] / chance2 if chance2 else None
    s1 = result2['f1'] >= .25
    s2 = result2['f1'] >= 2 * chance2
    s3 = result2['f1'] > controls['2']['oop_proxy']['f1']
    gate = dict(S1_f1_p2=result2['f1'], S2_ratio_to_chance=ratio,
                S3_beats_oop_proxy=s3, verdict='PASS' if s1 and s2 and s3 else 'FAIL')
    doc = {'job': 'P1 FootballShot: goal-end directed ball motion',
           'command': ' '.join(sys.argv),
           'period1_f1': result1['f1'], 'period2_f1': result2['f1'],
           'budget_K': chosen, 'chance_mean_f1': chance2,
           'oop_proxy_f1': controls['2']['oop_proxy']['f1'], 'gate': gate,
           'period1_vs_period2': {'period1_dev': result1, 'period2_heldout': result2},
           'chance': {p: c['chance'] for p, c in controls.items()},
           'oop_proxy': {p: c['oop_proxy'] for p, c in controls.items()},
           'budget_sweep': [dict(K=k, period1_f1=best[k][0]['f1'],
                                 period1_n_pred=best[k][0]['n_pred']) for k in caps[1:]],
           'unconstrained_period1': best[None][0], 'frozen_config': config,
           'frozen_config_sha256': freeze_hash,
           'protocol': dict(tolerance_s=tol, matcher='scripts/local/score-benchmark.py:match_one_type',
                            sweep_cells=cells, tuned_on='period1', heldout_evaluations=1,
                            budget_tolerance=a.budget_tolerance, random_seed_by_period=[12, 13],
                            team='omitted; team-aware F1 is zero',
                            candidates='CLI compatibility input; raw candidates not used',
                            end_anchors='period1 goal_xi; missing end uses existing GoalKick xi',
                            budget_fallback='unconstrained if no K meets relative tolerance'),
           'deviations': [],
           'caveats': ['Period boundaries are supplied by the benchmark.',
                       'Goal-end anchors are non-metric inherited restart positions.',
                       'Motion is a sparse-track cue; period1 fitting can overfit 14 events.']}
    preds = [{'video_s': t, 'event_type': TYPE, 'period': period}
             for period, times in ((1, pred1), (2, pred2)) for t in times]
    manifest = dict(attempted=[TYPE], tuned_on='period1',
                    not_attempted={t: 'Outside P1 shot package' for t in benchmark['events']['per_type'] if t != TYPE},
                    team='not predicted', save_outcome='cancelled by gate failure' if not (s1 and s2 and s3) else 'outside this file ownership')
    for path, data in ((a.pred, {'events': preds}), (a.manifest, manifest), (a.out, doc)):
        Path(path).write_text(json.dumps(data, indent=1, allow_nan=False) + '\n')
    print(json.dumps({'gate': gate}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
