"""Restricted timeline scheduling and composition; validation must stay native-free."""

import copy
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from reelforge.characters.presets import CharacterPreset
from reelforge.core.errors import InputError
from reelforge.environments.presets import EnvironmentPreset
from reelforge.environments.scene import camera_at, compose_layers, environment_frame, layers_at
from reelforge.rendering.model import RenderError
from reelforge.stories.contract import CAMERAS, load_story, validate_story
from reelforge.stories.sampling import sample_story, shot_camera, story_frame

EXAMPLE = Path("examples/stories/last_farm.json")
NATIVE = importlib.util.find_spec("cairo") is not None


@pytest.fixture
def data():
    return json.loads(EXAMPLE.read_text())


def test_example_roundtrip_and_frozen_types(data):
    story = validate_story(data)
    assert story.to_data() == data
    assert load_story(EXAMPLE) == story
    assert isinstance(story.shots, tuple)
    assert sum(s.frames for s in story.shots) == story.output.frames == 360


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "story-999"),
        (("output", "frames"), 901),
        (("output", "width"), 1440),
        (("output", "fps"), 60),
        (("output", "fps"), 30.0),
        (("output", "height"), True),
        (("output", "codec"), "vp9"),
        (("output", "pixel_format"), "rgba"),
        (("output", "frames"), math.inf),
        (("output", "frames"), False),
        (("title",), " "),
        (("title",), "x" * 121),
        (("shots", 0, "start_frame"), 1),
        (("shots", 1, "start_frame"), 119),
        (("shots", 1, "start_frame"), 121),
        (("shots", 0, "end_frame"), 0),
        (("shots", 0, "end_frame"), 29),
        (("shots", 0, "end_frame"), 301),
        (("shots", 0, "end_frame"), 120.0),
        (("shots", 0, "start_frame"), False),
        (("shots", 1, "id"), "quiet_orchard"),
        (("shots", 0, "id"), '__import__("os")'),
        (("shots", 0, "camera"), "eval(camera)"),
        (("shots", 0, "environment"), "elsewhere"),
        (("shots", 0, "transition"), "dissolve"),
        (("shots", 0, "character", "character"), "new_hero"),
        (("shots", 0, "character", "action"), "walk"),
        (("shots", 0, "character", "action"), "run"),
        (("shots", 0, "character", "expression"), "angry"),
        (("shots", 0, "character", "speed"), 2),
        (("shots", 0, "character", "intensity"), 0.49),
        (("shots", 0, "art_direction", "warmth"), math.nan),
        (("shots", 0, "art_direction", "atmosphere"), 1.01),
        (("shots", 0, "art_direction", "breeze"), True),
        (("shots", 0, "art_direction", "framing"), -1.01),
    ],
)
def test_reject_invalid_timeline_and_requests(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InputError) as caught:
        validate_story(data)
    assert caught.value.issue.path.startswith("/")
    assert caught.value.issue.message


@pytest.mark.parametrize(
    "location",
    [(), ("output",), ("shots", 0), ("shots", 0, "character"), ("shots", 0, "art_direction")],
)
def test_unknown_fields_rejected(data, location):
    target = data
    for key in location:
        target = target[key]
    target["python"] = '__import__("os").system("bad")'
    with pytest.raises(InputError):
        validate_story(data)


@pytest.mark.parametrize("shots", [[], None, {}, [None], [1] * 9])
def test_shot_list_bounds(data, shots):
    data["shots"] = shots
    with pytest.raises(InputError):
        validate_story(data)


def test_missing_fields_bad_nested_types_and_duration_disagreement(data):
    for mutate in (
        lambda d: d.pop("output"),
        lambda d: d["shots"][0].pop("transition"),
        lambda d: d["output"].update(frames=359),
        lambda d: d["shots"][0].update(character=[]),
        lambda d: d["shots"][0].update(art_direction=[]),
    ):
        d = copy.deepcopy(data)
        mutate(d)
        with pytest.raises(InputError):
            validate_story(d)


@pytest.mark.parametrize(
    "text",
    [
        '{"x":1,"x":2}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":1e9999}',
        "[" * 33 + "0" + "]" * 33,
        "not JSON",
    ],
)
def test_strict_json_parser(tmp_path, text):
    p = tmp_path / "bad.json"
    p.write_text(text)
    with pytest.raises(InputError):
        load_story(p)


def test_input_size_limit(tmp_path):
    p = tmp_path / "huge.json"
    p.write_bytes(b" " * (1048576 + 1))
    with pytest.raises(InputError) as e:
        load_story(p)
    assert e.value.issue.code == "INPUT_TOO_LARGE"


@pytest.mark.parametrize(
    "frame,index,local",
    [(0, 0, 0), (119, 0, 119), (120, 1, 0), (239, 1, 119), (240, 2, 0), (359, 2, 119)],
)
def test_exact_cut_boundaries(frame, index, local):
    story = load_story(EXAMPLE)
    s = sample_story(story, frame)
    assert s.shot == story.shots[index]
    assert s.local_frame == local
    assert s.progress == local / 119
    assert s.action_seconds == local / 30
    assert s.environment_seconds == frame / 30


@pytest.mark.parametrize("frame", [-1, 360, True, 0.5, math.nan])
def test_frame_domain(frame):
    with pytest.raises(RenderError):
        sample_story(load_story(EXAMPLE), frame)


def test_no_gap_overlap_or_endpoint_inclusion():
    story = load_story(EXAMPLE)
    counts = {s.id: 0 for s in story.shots}
    for f in range(360):
        sample = sample_story(story, f)
        counts[sample.shot.id] += 1
        assert sum(s.start_frame <= f < s.end_frame for s in story.shots) == 1
    assert list(counts.values()) == [120] * 3


def test_independent_duration_and_local_clocks(data):
    data["shots"][0]["end_frame"] = 60
    data["shots"][1].update(start_frame=60, end_frame=240)
    story = validate_story(data)
    for shot in story.shots:
        assert sample_story(story, shot.start_frame).progress == 0
        assert sample_story(story, shot.end_frame - 1).progress == 1
    assert sample_story(story, 60).action_seconds == 0
    assert sample_story(story, 60).environment_seconds == 2
    assert sample_story(story, 239).action_seconds == 179 / 30
    # Camera endpoint depends on normalized shot progress, not a hidden six-second clip.
    baseline = load_story(EXAMPLE)
    assert sample_story(story, 59).camera == sample_story(baseline, 119).camera


@pytest.mark.parametrize("camera", CAMERAS)
def test_sampling_order_and_camera_bounds(data, camera):
    data["shots"][1]["camera"] = camera
    story = validate_story(data)
    expected = story_frame(story, 180)
    story_frame(story, 359)
    assert expected == story_frame(story, 180)
    for progress in (0, 0.25, 0.5, 0.75, 1):
        c = shot_camera(story.shots[1], progress)
        assert 0.95 <= c.zoom <= 2.3 and -12 <= c.x <= 102
        assert c.transform(1).sx == c.transform(1).sy
        assert c.transform(1.4).sx != c.transform(0.18).sx
    with pytest.raises(RenderError):
        shot_camera(story.shots[1], 1.01)


def test_three_compositions_have_distinct_story_targets():
    story = load_story(EXAMPLE)
    wide, reaction, reveal = [sample_story(story, f).camera for f in (60, 180, 300)]
    assert wide.zoom < reaction.zoom < reveal.zoom
    character = reaction.transform(1)
    assert 90 < character.tx + 165 * character.sx < 160
    assert 230 < character.ty + 350 * character.sy < 310
    door = reveal.transform(0.85)
    assert 185 < door.tx + 231 * door.sx < 240
    assert 270 < door.ty + 365 * door.sy < 330
    # Same viewing side: Rowan remains left of the threshold across every cut.
    for f in (0, 119, 120, 239, 240, 359):
        c = sample_story(story, f).camera
        a, b = c.transform(1), c.transform(0.85)
        assert a.tx + 165 * a.sx < b.tx + 231 * b.sx


@pytest.mark.parametrize("action", ["idle", "look_around", "react"])
@pytest.mark.parametrize("direction", ["left", "right"])
def test_existing_character_presets_and_ground_plane(data, action, direction):
    data["shots"][1]["character"].update(
        action=action, direction=direction, expression="determined"
    )
    story = validate_story(data)
    s = sample_story(story, 180)
    layers = compose_layers(
        s.shot.environment,
        s.camera,
        s.environment_seconds,
        s.shot.character,
        acting_seconds=s.action_seconds,
    )
    assert {x.depth for x in layers if x.id in ("rowan", "ground", "fence_props")} == {1}
    assert [x.id for x in layers].index("rowan") > [x.id for x in layers].index("door_light")
    assert len(story_frame(story, 180)) < 1500


def test_old_environment_wrapper_is_same_clock_and_actor():
    p = EnvironmentPreset()
    assert layers_at(p, 90) == compose_layers(
        p, camera_at(p, 90), 3, CharacterPreset(action="look_around", expression="concerned")
    )
    assert len(environment_frame(179)) < 1500


def test_validator_has_no_native_or_media_dependency(tmp_path):
    script = """
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname == 'cairo' or fullname.startswith('reelforge.media'):
   raise AssertionError('validation loaded native/media code')
sys.meta_path.insert(0,Block())
from reelforge.stories.contract import load_story
s=load_story('examples/stories/last_farm.json')
assert s.output.frames == 360
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


def test_invalid_cli_does_not_create_output_directory(tmp_path):
    p = tmp_path / "invalid.json"
    p.write_text("{}")
    output = tmp_path / "do-not-create"
    result = subprocess.run(
        [sys.executable, "tools/render_story.py", str(p), "--output-dir", str(output)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["ok"] is False
    assert not output.exists()


def test_hashseed_independent_story_sampling():
    script = (
        "from reelforge.stories.contract import load_story; "
        "from reelforge.stories.sampling import sample_story; "
        'print(sample_story(load_story("examples/stories/last_farm.json"),180))'
    )
    values = [
        subprocess.check_output(
            [sys.executable, "-c", script], text=True, env={**os.environ, "PYTHONHASHSEED": str(i)}
        )
        for i in (2, 81)
    ]
    assert values[0] == values[1]


def test_minimum_maximum_and_eight_shot_limits_are_usable(data):
    short = copy.deepcopy(data)
    short["shots"] = short["shots"][:1]
    short["shots"][0]["end_frame"] = short["output"]["frames"] = 30
    assert sample_story(validate_story(short), 29).progress == 1
    long = copy.deepcopy(data)
    long["output"]["frames"] = 900
    for i, shot in enumerate(long["shots"]):
        shot.update(start_frame=i * 300, end_frame=(i + 1) * 300)
    assert sample_story(validate_story(long), 899).action_seconds == 299 / 30
    many = copy.deepcopy(data)
    many["shots"] = [copy.deepcopy(data["shots"][0]) for _ in range(8)]
    for i, shot in enumerate(many["shots"]):
        shot.update(id=f"shot_{i}", start_frame=i * 30, end_frame=(i + 1) * 30)
    many["output"]["frames"] = 240
    assert sample_story(validate_story(many), 239).shot.id == "shot_7"
