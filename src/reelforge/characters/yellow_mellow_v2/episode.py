"""Episode adapter: drive the real Yellow Mellow V2 rig from accepted blocking segments.

The blocking contract already solves a character-agnostic world root trajectory (RouteClock)
and a left/right facing per 90-frame segment. This module turns the *same* segment list into a
Yellow Mellow V2 ``Performance`` (its genuine rig, IK, expressions, motion presets and pose
blending) and exposes a per-frame drawer with the exact shape of ``rowan.draw_character``:
local geometry authored at the ground origin (0, 0), facing +X, mirrored by ``direction`` and
scaled uniformly by the caller. Root travel is applied here so the body sits on the solved
route; the blocking/camera layers remain unchanged.

Only registered action/expression ids and bounded numbers reach V2; nothing executable, no
paths and no manifest-supplied geometry are ever accepted.
"""

from __future__ import annotations

from dataclasses import dataclass

from reelforge.rendering.model import DrawPath, RenderError

from .artwork import Placement as ArtPlacement
from .artwork import character_commands, contact_shadows
from .character import ActionRequest, Performance, YellowMellowV2
from .expressions import EXPRESSIONS
from .rig import STANDING_HEIGHT

# Rowan's artwork is authored at roughly ROWAN_REFERENCE_HEIGHT logical units at draw scale 1,
# then multiplied by the shared blocking plan scale (0.35..0.75). Drawing Yellow Mellow at this
# ratio makes the two characters occupy a comparable fraction of frame under the same plan scale.
ROWAN_REFERENCE_HEIGHT = 95.0
DEFAULT_DRAW_SCALE = ROWAN_REFERENCE_HEIGHT / STANDING_HEIGHT

# Blocking modes -> V2 action vocabulary. Acting verbs map to expressive presets that keep the
# feet planted (the route is stationary during idle/turn segments).
ACTING_TO_ACTION = {
    "idle": "idle",
    "look_around": "look",
    "react": "surprise",
    "none": None,
}

# Rowan-contract expressions do not all exist for Yellow Mellow; map the six accepted blocking
# expressions onto the nearest V2 FaceState so a storyboard authored for either character reads
# sensibly. Yellow Mellow's own eight expressions are also accepted directly.
ROWAN_EXPRESSION_ALIAS = {
    "calm": "neutral",
    "concerned": "concerned",
    "focused": "determined",
    "surprised": "surprised",
    "frightened": "surprised",
    "determined": "determined",
}


def resolve_expression(name: str) -> str:
    """Accept a V2 expression id directly, or map a Rowan-contract expression onto one."""
    if name in EXPRESSIONS:
        return name
    if name in ROWAN_EXPRESSION_ALIAS:
        return ROWAN_EXPRESSION_ALIAS[name]
    raise RenderError(f"Unknown expression {name!r} for yellow_mellow_v2")


@dataclass(frozen=True)
class SegmentSpec:
    """The subset of an accepted blocking Segment this adapter consumes."""

    start: int
    end: int
    mode: str
    acting: str
    expression: str
    facing: str
    distance_units: float  # signed world-unit travel across the segment at the plan scale


def _facing_value(facing: str) -> float:
    return 0.92 if facing == "right" else -0.92


def requests_from_segments(specs: tuple[SegmentSpec, ...]) -> tuple[list[ActionRequest], str, str]:
    """Map 90 frames of blocking segments to V2 ActionRequests.

    Returns (requests, start_expression, start_facing). Durations always sum to 90 frames so the
    Performance is frame-aligned with the storyboard segment. Locomotion runs of walk/run/stop
    are emitted as consecutive locomotion requests (V2 merges them into one continuous clip).
    """
    if not specs:
        raise RenderError("A storyboard segment needs at least one blocking sub-segment")
    requests: list[ActionRequest] = []
    start_facing = specs[0].facing
    start_expression = resolve_expression(specs[0].expression)
    for spec in specs:
        duration = spec.end - spec.start
        if duration < 2:
            raise RenderError("Blocking sub-segment shorter than 2 frames is unsupported")
        expr = resolve_expression(spec.expression)
        is_terminal = spec is specs[-1]
        if spec.mode in ("walk", "run"):
            params = {"direction": spec.facing}
            # The blocking route owns absolute world X. If a moving segment is the final one
            # (e.g. an escape that exits still moving), request a V2 stop so the clip resolves to
            # planted feet by frame 90 instead of being cut mid-stride; the body still follows the
            # route via the per-frame Placement, so no sliding is introduced beyond V2's small
            # residual pelvis travel.
            if is_terminal:
                params["stop"] = True
            requests.append(ActionRequest(spec.mode, duration, expression=expr, params=params))
        elif spec.mode == "stop":
            requests.append(
                ActionRequest(
                    "walk",
                    duration,
                    expression=expr,
                    params={"direction": spec.facing, "stop": True},
                )
            )
        elif spec.mode == "turn":
            # A planted turn to the new facing; V2 turns on the spot.
            to = "right" if spec.facing == "right" else "left"
            requests.append(ActionRequest("turn", duration, expression=expr, params={"to": to}))
        else:  # idle
            action = ACTING_TO_ACTION.get(spec.acting, "idle") or "idle"
            # surprise/look validate a 12-frame minimum upstream in blocking already.
            requests.append(ActionRequest(action, duration, expression=expr))
    return requests, start_expression, start_facing


class YellowMellowDrawer:
    """Per-frame Rowan-shaped drawer backed by a real V2 Performance for one 90-frame segment.

    ``commands(frame, direction)`` returns local geometry at the ground origin (0, 0) with unit
    draw scale and the requested facing, exactly like ``rowan.draw_character(position=(0,0),
    scale=1)``. The blocking layer then wraps it in ``Placement(route_x, plan.y, plan.scale)``.

    V2 bakes a little locomotion travel into ``pelvis_x``; the blocking route owns absolute world
    X, so we only keep V2's *residual* within-segment pelvis motion as local sway and draw the
    body at a near-origin local X. This avoids double-counting travel while preserving the weight
    shift V2 produces.
    """

    def __init__(self, specs: tuple[SegmentSpec, ...], *, draw_scale: float, seed: str):
        requests, start_expr, start_facing = requests_from_segments(specs)
        self._perf: Performance = YellowMellowV2(
            facing=_facing_value(start_facing), seed=seed
        ).animate(requests, start_expression=start_expr)
        if self._perf.frames != 90:
            raise RenderError(
                f"Yellow Mellow segment must animate exactly 90 frames, got {self._perf.frames}"
            )
        self._draw_scale = draw_scale

    def commands(self, frame: int, direction: str) -> tuple[DrawPath, ...]:
        if type(frame) is not int or not 0 <= frame < 90:
            raise RenderError("Yellow Mellow drawer frame must be an integer 0..89")
        if direction not in ("left", "right"):
            raise RenderError("direction must be left/right")
        cf = self._perf.sample(frame)
        sign = 1 if direction == "right" else -1
        # The blocking route owns absolute world X, so the body is drawn at the local ground
        # origin. V2's baked locomotion travel (pelvis_x) is intentionally dropped here to avoid
        # double-counting horizontal motion and any resulting foot slide; vertical pelvis motion
        # (bob, crouch, jump) and the planted-foot contacts are kept by sampling the pose as-is.
        placement = ArtPlacement(0.0, 0.0, self._draw_scale, sign)
        shadows = contact_shadows(cf.state, placement)
        body = character_commands(cf.state, cf.face, placement)
        return shadows + body


def build_drawer(specs, *, draw_scale: float = DEFAULT_DRAW_SCALE, seed: str = "yellow_mellow_v2"):
    return YellowMellowDrawer(tuple(specs), draw_scale=draw_scale, seed=seed)
