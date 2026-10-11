import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/local/detect-ball-tiles.py"
spec = importlib.util.spec_from_file_location("ball_tiles", SCRIPT)
tiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tiles)


class Tensor:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class FakeImage:
    """Frame or crop stand-in: records its frame-coordinate origin and size."""

    def __init__(self, width, height, x0=0, y0=0):
        self.shape = (height, width, 3)
        self.origin = (x0, y0)

    def __getitem__(self, key):
        ys, xs = key
        return FakeImage(xs.stop - xs.start, ys.stop - ys.start,
                         self.origin[0] + xs.start, self.origin[1] + ys.start)


def covered(width, height, grid):
    grid_cells = set()
    for x0, y0, x1, y1 in grid:
        for y in range(y0, y1):
            for x in range(x0, x1):
                grid_cells.add((x, y))
    return len(grid_cells) == width * height


@pytest.fixture
def env(tmp_path, monkeypatch):
    directory = tmp_path / "pilot"
    directory.mkdir()
    (directory / "clip.mp4").write_bytes(b"local clip")
    prep = {"artifact_type": "video_pilot_preparation", "inference_performed": False,
            "input_provenance": {"mode": "video_only", "evaluation_labels_used": False,
                                 "video_sha256": "a" * 64},
            "sampling": {"start_s": 120, "fps": 10, "duration_s": .3},
            "clip": {"sha256": hashlib.sha256(b"local clip").hexdigest()}}
    (directory / "pilot_manifest.json").write_text(json.dumps(prep))
    weights = tmp_path / "checkpoint.pt"
    weights.write_bytes(b"checkpoint")
    state = SimpleNamespace(calls=[], opened=[], frames=3, size=(100, 61), script=None)

    class Model:
        names = {0: "person", 32: "sports ball"}

        def predict(self, **kwargs):
            state.calls.append(kwargs)
            out = []
            for image in kwargs["source"]:
                found = state.script(image) if state.script else []
                boxes = SimpleNamespace(xyxy=Tensor([f[0] for f in found]), conf=Tensor([f[1] for f in found]),
                                        cls=Tensor([f[2] if len(f) > 2 else 32 for f in found]))
                out.append(SimpleNamespace(boxes=boxes if found else None))
            return out

    def open_frames(path):
        state.opened.append(path)
        for _ in range(state.frames):
            yield FakeImage(*state.size)

    monkeypatch.setattr(tiles, "load_model", lambda _: (Model(), {"ultralytics": "mock", "torch": "mock"}))
    monkeypatch.setattr(tiles, "open_frames", open_frames)
    state.directory, state.weights, state.prep_path = directory, weights, directory / "pilot_manifest.json"
    return state


def run(env, tmp_path, **kw):
    out = tmp_path / "out"
    manifest = tiles.detect_ball_tiles(env.directory, env.weights, out, **kw)
    return out, json.loads(manifest.read_text())


# ---- tile geometry -------------------------------------------------------

@pytest.mark.parametrize("w,h,nx,ny,ov", [(100, 60, 3, 2, .15), (1280, 720, 3, 2, .15), (101, 59, 3, 2, .15),
                                         (97, 53, 4, 5, .5), (1921, 1081, 7, 3, 0), (10, 10, 1, 1, .3),
                                         (7, 5, 7, 5, .9)])
def test_tile_grid_covers_every_pixel_edge_aligned(w, h, nx, ny, ov):
    grid = tiles.tile_grid(w, h, nx, ny, ov)
    assert len(grid) == nx * ny
    assert covered(w, h, grid)
    assert min(t[0] for t in grid) == 0 and min(t[1] for t in grid) == 0
    assert max(t[2] for t in grid) == w and max(t[3] for t in grid) == h
    assert all(0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h for x0, y0, x1, y1 in grid)
    assert grid == tiles.tile_grid(w, h, nx, ny, ov)


def test_tile_grid_overlap_and_row_major_order():
    grid = tiles.tile_grid(100, 60, 3, 2, .15)
    assert grid[0][:2] == (0, 0) and grid[2][2] == 100 and grid[3][:2][0] == 0 and grid[3][3] == 60
    assert grid[0][2] > grid[1][0]  # horizontal neighbours overlap


@pytest.mark.parametrize("args", [(100, 60, 0, 2, .1), (100, 60, 2, 0, .1), (100, 60, 2, 2, -.1),
                                  (100, 60, 2, 2, 1), (100, 60, 2, 2, float("nan")), (4, 60, 5, 2, .1),
                                  (100, 60, 2.0, 2, .1), (0, 60, 1, 1, 0)])
def test_tile_grid_rejects_invalid(args):
    with pytest.raises(ValueError):
        tiles.tile_grid(*args)


def test_offset_back_to_frame_and_clip():
    assert tiles.offset_box([1, 2, 5, 6], 30, 20, 100, 60) == [31, 22, 35, 26]
    assert tiles.offset_box([-5, 0, 10, 50], 90, 40, 100, 60) == [85, 40, 100, 60]
    assert tiles.offset_box([200, 0, 210, 5], 0, 0, 100, 60) is None


# ---- NMS -----------------------------------------------------------------

def cand(box, conf, source):
    return {"bbox": box, "conf": conf, "source": source}


def test_duplicate_suppression_and_input_order_determinism():
    pool = [cand([10, 10, 20, 20], .5, 2), cand([10, 10, 20, 20], .5, "full"), cand([11, 10, 21, 20], .9, 0),
            cand([50, 50, 58, 58], .4, 1), cand([10, 10, 20, 20], .5, 1)]
    first = tiles.nms(pool)
    assert [c["conf"] for c in first] == [.9, .4]
    for order in (pool[::-1], pool[2:] + pool[:2]):
        assert tiles.nms(order) == first
    tie = tiles.nms([cand([0, 0, 5, 5], .5, 3), cand([0, 0, 5, 5], .5, "full")])
    assert tie == [cand([0, 0, 5, 5], .5, "full")]


def test_top_k_cap_keeps_highest_confidence():
    pool = [cand([i * 10, 0, i * 10 + 4, 4], .3 + i / 100, "full") for i in range(30)]
    kept = tiles.nms(pool)
    assert len(kept) == tiles.TOP_K
    assert kept[0]["conf"] == pytest.approx(.59) and kept[-1]["conf"] == pytest.approx(.40)


# ---- end to end with fake runtime ----------------------------------------

def test_pipeline_offsets_dedups_and_timestamps(env, tmp_path):
    grid = tiles.tile_grid(100, 61, 3, 2, .15)

    def script(image):
        # one ball at frame (50, 30)-(56, 36), seen by every image that fully contains it
        x0, y0 = image.origin
        h, w = image.shape[:2]
        if x0 <= 50 and y0 <= 30 and 56 <= x0 + w and 36 <= y0 + h:
            return [([50 - x0, 30 - y0, 56 - x0, 36 - y0], .8 if image.origin == (0, 0) and w == 100 else .6)]
        return []

    env.script = script
    out, manifest = run(env, tmp_path)
    data = json.loads((out / "ball_candidates.json").read_text())["detections"]
    assert [row["t"] for row in data] == pytest.approx([120, 120.1, 120.2])
    assert all(row["w"] == 100 and row["h"] == 61 for row in data)
    for row in data:
        assert len(row["candidates"]) == 1  # duplicates from overlapping tiles suppressed
        c = row["candidates"][0]
        assert c["bbox"] == [50, 30, 56, 36] and c["source"] == "full" and c["frame"] == row["frame"]
        assert (c["cx"], c["cy"], c["size"]) == (53, 33, 6)
    assert manifest["counts"]["raw_candidates"] > manifest["counts"]["ball_candidates"] == 3
    assert manifest["config"]["tiles"]["grid"] == [list(t) for t in grid]
    assert manifest["status"] == "complete"
    assert {p.name for p in out.iterdir()} == {"ball_candidates.json", "detection_manifest.json"}


def test_tile_only_detection_uses_tile_source_and_frame_coords(env, tmp_path):
    grid = tiles.tile_grid(100, 61, 3, 2, .15)
    target = 4

    def script(image):
        if image.origin == grid[target][:2] and image.shape[1] == grid[target][2] - grid[target][0]:
            return [([1, 2, 5, 6], .7)]
        return []

    env.script = script
    out, _ = run(env, tmp_path)
    c = json.loads((out / "ball_candidates.json").read_text())["detections"][0]["candidates"][0]
    assert c["source"] == target
    assert c["bbox"] == [grid[target][0] + 1, grid[target][1] + 2, grid[target][0] + 5, grid[target][1] + 6]


def test_batch_size_bounded_and_ball_class_cpu_only(env, tmp_path):
    run(env, tmp_path, nx=3, ny=3)  # 10 images per frame
    assert env.calls and all(len(c["source"]) <= tiles.BATCH_SIZE <= 6 for c in env.calls)
    assert sum(len(c["source"]) for c in env.calls) == 3 * 10
    assert all(c["classes"] == [32] and c["device"] == "cpu" and c["verbose"] is False for c in env.calls)
    assert all(c["imgsz"] == 640 and c["conf"] == .25 for c in env.calls)


def test_partial_max_frames_manifest(env, tmp_path):
    out, manifest = run(env, tmp_path, max_frames=2)
    assert manifest["status"] == "partial"
    assert manifest["coverage"]["frames_processed"] == 2 and manifest["coverage"]["expected_frames"] == 3
    assert manifest["coverage"]["stream_exhausted"] is False
    assert len(json.loads((out / "ball_candidates.json").read_text())["detections"]) == 2


@pytest.mark.parametrize("frames,ok", [(3, True), (2, True), (4, True), (1, False), (6, False)])
def test_count_integrity_for_complete_runs(env, tmp_path, frames, ok):
    env.frames = frames
    if ok:
        assert run(env, tmp_path)[1]["status"] == "complete"
    else:
        with pytest.raises(ValueError, match="decoded frame count"):
            run(env, tmp_path)
        assert not (tmp_path / "out").exists()


def test_inconsistent_frame_size_rejected_without_output(env, tmp_path, monkeypatch):
    def frames(path):
        yield FakeImage(100, 61)
        yield FakeImage(100, 60)

    monkeypatch.setattr(tiles, "open_frames", frames)
    with pytest.raises(ValueError, match="expected 100x61"):
        run(env, tmp_path)
    assert not (tmp_path / "out").exists()


def test_tiles_larger_than_frame_grid_rejected(env, tmp_path):
    env.size = (2, 61)
    with pytest.raises(ValueError, match="finer than the frame"):
        run(env, tmp_path, nx=3)


# ---- validation before decode/inference ----------------------------------

def rewrite(env, mutate):
    manifest = json.loads(env.prep_path.read_text())
    mutate(manifest)
    env.prep_path.write_text(json.dumps(manifest))


def assert_untouched(env, tmp_path):
    assert not env.calls and not env.opened and not (tmp_path / "out").exists()


def test_tampered_clip_rejected(env, tmp_path):
    (env.directory / "clip.mp4").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="clip hash"):
        run(env, tmp_path)
    assert_untouched(env, tmp_path)


@pytest.mark.parametrize("mutate", [
    lambda m: m["input_provenance"].update(video_sha256="invalid"),
    lambda m: m["input_provenance"].update(evaluation_labels_used=True),
    lambda m: m["input_provenance"].update(evaluation_labels_used=None),
    lambda m: m["input_provenance"].update(mode="ml"),
    lambda m: m.update(inference_performed=True),
    lambda m: m.update(inference_performed=None),
    lambda m: m.update(artifact_type="other"),
    lambda m: m["sampling"].update(fps=0),
    lambda m: m["sampling"].update(duration_s=-1),
    lambda m: m["sampling"].update(start_s=-1),
    lambda m: m["sampling"].update(fps=True),
    lambda m: m["sampling"].update(start_s="nan"),
    lambda m: m["sampling"].pop("fps"),
])
def test_invalid_manifest_rejected(env, tmp_path, mutate):
    rewrite(env, mutate)
    with pytest.raises(ValueError):
        run(env, tmp_path)
    assert_untouched(env, tmp_path)


def test_symlinked_inputs_rejected(env, tmp_path):
    link = tmp_path / "pilot-link"
    link.symlink_to(env.directory)
    with pytest.raises(ValueError, match="symlink"):
        tiles.detect_ball_tiles(link, env.weights, tmp_path / "out")
    real = tmp_path / "real.mp4"
    (env.directory / "clip.mp4").rename(real)
    (env.directory / "clip.mp4").symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        run(env, tmp_path)
    assert_untouched(env, tmp_path)


def test_output_must_be_new(env, tmp_path):
    (tmp_path / "out").mkdir()
    with pytest.raises(ValueError, match="overwrite"):
        run(env, tmp_path)
    assert not env.calls and not env.opened


def test_dangling_output_symlink_rejected(env, tmp_path):
    (tmp_path / "out").symlink_to(tmp_path / "absent")
    with pytest.raises(ValueError, match="overwrite"):
        run(env, tmp_path)
    assert not env.calls and not env.opened


@pytest.mark.parametrize("weights", ["https://example.com/m.pt", "missing.pt", "model.bin"])
def test_weights_must_be_local_existing_pt(env, tmp_path, weights):
    (tmp_path / "model.bin").write_bytes(b"x")
    target = weights if weights.startswith("http") else tmp_path / weights
    with pytest.raises(ValueError):
        tiles.detect_ball_tiles(env.directory, target, tmp_path / "out")
    assert not env.calls and not env.opened


@pytest.mark.parametrize("names", [{32: "person"}, {0: "sports ball"}, None])
def test_wrong_ball_class_name_rejected_before_decode(env, tmp_path, monkeypatch, names):
    original = tiles.load_model

    def load(weights):
        model, versions = original(weights)
        model.names = names
        return model, versions

    monkeypatch.setattr(tiles, "load_model", load)
    with pytest.raises(ValueError, match="class 32"):
        run(env, tmp_path)
    assert_untouched(env, tmp_path)


@pytest.mark.parametrize("kw", [{"nx": 0}, {"ny": 0}, {"overlap": 1}, {"overlap": -.1}, {"imgsz": 0},
                                {"conf": 1.5}, {"max_frames": 0}, {"overlap": float("nan")}])
def test_invalid_parameters_rejected(env, tmp_path, kw):
    with pytest.raises(ValueError):
        run(env, tmp_path, **kw)
    assert_untouched(env, tmp_path)


def test_manifest_provenance_and_limitations(env, tmp_path):
    out, manifest = run(env, tmp_path)
    assert manifest["artifact_type"] == "video_pilot_tiled_ball_candidates"
    prov = manifest["input_provenance"]
    assert prov["mode"] == "video_only" and prov["evaluation_labels_used"] is False
    assert prov["video_sha256"] == "a" * 64 and prov["clip_sha256"] == hashlib.sha256(b"local clip").hexdigest()
    assert manifest["model"]["sha256"] == hashlib.sha256(b"checkpoint").hexdigest()
    assert manifest["pilot_manifest_sha256"] == hashlib.sha256(env.prep_path.read_bytes()).hexdigest()
    assert manifest["config"]["top_k_per_frame"] == tiles.TOP_K and manifest["config"]["batch_size"] == tiles.BATCH_SIZE
    assert any("not precision or recall" in s for s in manifest["limitations"])
    with pytest.raises(FileExistsError):  # outputs written exclusively
        (out / "ball_candidates.json").open("x")


# ---- review fixes --------------------------------------------------------

@pytest.mark.parametrize("size,nx,ny", [((100, 61), 3, 3), ((101, 59), 4, 5), ((64, 48), 1, 1)])
def test_every_predict_call_has_uniform_shapes_and_full_frame_alone(env, tmp_path, size, nx, ny):
    env.size = size
    run(env, tmp_path, nx=nx, ny=ny)
    for call in env.calls:
        assert len({tuple(i.shape) for i in call["source"]}) == 1
        assert len(call["source"]) <= tiles.BATCH_SIZE
    full_calls = [c for c in env.calls if tuple(c["source"][0].shape)[:2] == (size[1], size[0])]
    assert all(len(c["source"]) == 1 for c in full_calls) and len(full_calls) >= env.frames
    assert sum(len(c["source"]) for c in env.calls) == env.frames * (1 + nx * ny)


def test_nonuniform_tiles_are_grouped_by_shape(env, tmp_path, monkeypatch):
    grid = [(0, 0, 50, 61), (50, 0, 100, 61)] + [(0, 0, 30, 61)] * 2 + [(0, 0, 40, 61)]
    monkeypatch.setattr(tiles, "tile_grid", lambda *a: grid)
    env.frames = 3
    run(env, tmp_path)
    for call in env.calls:
        assert len({tuple(i.shape) for i in call["source"]}) == 1


def test_max_frames_covering_whole_clip_is_complete(env, tmp_path):
    _, manifest = run(env, tmp_path, max_frames=3)
    assert manifest["status"] == "complete" and manifest["coverage"]["stream_exhausted"] is True
    assert manifest["frame_integrity"]["holds"] is True


def test_max_frames_larger_than_clip_with_bad_count_stays_partial(env, tmp_path):
    env.frames = 1  # expected 3, tolerance 1 -> integrity fails
    _, manifest = run(env, tmp_path, max_frames=10)
    assert manifest["status"] == "partial" and manifest["frame_integrity"]["holds"] is False
    assert manifest["coverage"]["frames_processed"] == 1


def test_max_frames_larger_than_clip_with_ok_count_is_complete(env, tmp_path):
    env.frames = 2
    assert run(env, tmp_path, max_frames=10)[1]["status"] == "complete"


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(clip="x"), lambda m: m.update(clip=None), lambda m: m.update(clip=[1]),
    lambda m: m.update(sampling="x"), lambda m: m.update(sampling=[1]),
    lambda m: m.update(input_provenance="x"), lambda m: m.update(input_provenance=None),
    lambda m: m.update(input_provenance=[]),
])
def test_non_dict_fields_raise_value_error(env, tmp_path, mutate):
    rewrite(env, mutate)
    with pytest.raises(ValueError):
        run(env, tmp_path)
    assert_untouched(env, tmp_path)


def test_manifest_not_an_object_rejected(env, tmp_path):
    env.prep_path.write_text("[]")
    with pytest.raises(ValueError):
        run(env, tmp_path)


def test_main_reports_type_errors_cleanly(env, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise TypeError("odd")

    monkeypatch.setattr(tiles, "detect_ball_tiles", boom)
    with pytest.raises(SystemExit) as exc:
        tiles.main(["--pilot", "p", "--weights", "w", "--out", "o"])
    assert exc.value.code == 2


def test_failure_leaves_no_output_or_temp_dirs(env, tmp_path):
    env.frames = 9  # integrity failure before writing
    with pytest.raises(ValueError):
        run(env, tmp_path)
    assert not (tmp_path / "out").exists() and not [p for p in tmp_path.iterdir() if p.name.startswith(".out")]


def test_write_failure_cleans_staging(env, tmp_path, monkeypatch):
    monkeypatch.setattr(tiles.os, "rename", lambda *a: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(OSError):
        run(env, tmp_path)
    assert not (tmp_path / "out").exists() and not [p for p in tmp_path.iterdir() if p.name.startswith(".out")]


def test_success_leaves_only_final_dir(env, tmp_path):
    run(env, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(".")) == []


def test_symlinked_weights_rejected(env, tmp_path):
    link = tmp_path / "link.pt"
    link.symlink_to(env.weights)
    with pytest.raises(ValueError, match="symlink"):
        tiles.detect_ball_tiles(env.directory, link, tmp_path / "out")
    assert_untouched(env, tmp_path)


def test_non_ball_class_from_model_is_ignored(env, tmp_path):
    env.script = lambda image: [([1, 1, 5, 5], .9, 0), ([float("nan")] * 4, float("nan"), 0)] \
        if image.shape[1] == 100 else []
    out, manifest = run(env, tmp_path)
    assert manifest["counts"]["ball_candidates"] == 0
    assert "NaN" not in (out / "ball_candidates.json").read_text()


@pytest.mark.parametrize("found", [([1, 1, 5, 5], float("nan")), ([1, 1, 5, 5], float("inf")),
                                   ([float("nan"), 1, 5, 5], .5), ([1, 1, float("inf"), 5], .5)])
def test_non_finite_ball_output_rejected_without_output(env, tmp_path, found):
    env.script = lambda image: [found] if image.shape[1] == 100 else []
    with pytest.raises(ValueError, match="non-finite"):
        run(env, tmp_path)
    assert not (tmp_path / "out").exists()
