"""Public API: instantiate Yellow Mellow V2, request actions, sample and draw any frame.

Example::

    from reelforge.characters.yellow_mellow_v2 import ActionRequest, YellowMellowV2

    mellow = YellowMellowV2()
    show = mellow.animate([
        ActionRequest("wave", 40, expression="happy"),
        ActionRequest("hands_up", 30, expression="excited"),
        ActionRequest("walk", 60, params={"direction": "right"}),
        ActionRequest("stop", 20),
    ])
    commands = show.draw(frame=25, stage=Stage(x=180, ground_y=575, scale=2.3))

Requests contain only a registered action name, an integer duration, an optional expression
name and bounded preset parameters. Unknown actions, parameters or expressions are errors.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field

from reelforge.rendering.model import DrawPath, RenderError, finite

from .artwork import Placement, character_commands, contact_shadows
from .expressions import (
    FaceState,
    adjust,
    blend_faces,
    blink_amount,
    blink_starts,
    expression,
)
from .motions import (
    LOCOMOTION_ACTIONS,
    PRESETS,
    Clip,
    ClipStart,
    LocomotionClip,
    LocoSegment,
)
from .rig import RigState, Secondary, evaluate, smoothstep, standing_pose

MAX_FRAMES = 18000
PRIMARY_CACHE = 48  # bounded per-performance cache of primary rig states (documented budget)
SPRING_TAPS = 16


@dataclass(frozen=True)
class ActionRequest:
    action: str
    duration_frames: int
    expression: str | None = None
    params: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.action, str):
            raise RenderError("action must be a string")
        if type(self.duration_frames) is not int or not 2 <= self.duration_frames <= 3600:
            raise RenderError("duration_frames must be an integer in 2..3600")
        if self.expression is not None:
            expression(self.expression)
        for key, value in dict(self.params).items():
            if not isinstance(key, str):
                raise RenderError("parameter names must be strings")
            if not isinstance(value, (int, float, str, bool)):
                raise RenderError(f"parameter {key!r} must be a number, string or bool")


@dataclass(frozen=True)
class Stage:
    """Logical-frame placement: world x of character origin, ground line, scale, camera."""

    x: float = 180.0
    ground_y: float = 575.0
    scale: float = 2.3
    camera_x: float = 0.0

    def __post_init__(self):
        finite(self.x, self.ground_y, self.scale, self.camera_x)
        if not 0.2 <= self.scale <= 6:
            raise RenderError("stage scale must be 0.2..6")

    def frame_x(self, world_units: float) -> float:
        return self.x + self.scale * world_units - self.camera_x


@dataclass(frozen=True)
class Entry:
    start: int
    request_index: int
    clip: Clip
    face_in: FaceState
    targets: tuple[tuple[int, FaceState], ...]  # (local start frame, expression target)
    action: str


@dataclass(frozen=True)
class CharacterFrame:
    frame: int
    action: str
    state: RigState
    face: FaceState
    blink: float


class Performance:
    """A sampled timeline. Random access; deterministic for a given request list and seed."""

    def __init__(self, entries: list[Entry], frames: int, seed: str):
        self.entries = entries
        self.frames = frames
        self.seed = seed
        self._blinks = blink_starts(seed, frames)
        self._starts = [e.start for e in entries]
        self._cache: OrderedDict[int, RigState] = OrderedDict()

    # -- lookup
    def entry_at(self, frame: int) -> Entry:
        if not 0 <= frame < self.frames:
            raise RenderError(f"frame {frame} outside 0..{self.frames - 1}")
        lo = 0
        for i, s in enumerate(self._starts):
            if s <= frame:
                lo = i
        return self.entries[lo]

    def action_at(self, frame: int) -> str:
        return self.entry_at(frame).action

    def pose(self, frame: float):
        f = clamp_frame(frame, self.frames)
        e = self.entry_at(int(math.floor(f)) if f < self.frames else self.frames - 1)
        return e.clip.pose(f - e.start)

    def _primary(self, frame: int) -> RigState:
        frame = max(0, min(self.frames - 1, frame))
        if frame in self._cache:
            self._cache.move_to_end(frame)
            return self._cache[frame]
        state = evaluate(self.pose(frame))
        self._cache[frame] = state
        if len(self._cache) > PRIMARY_CACHE:
            self._cache.popitem(last=False)
        return state

    # -- secondary follow-through (damped spring convolution of base acceleration)
    def secondary(self, frame: int) -> Secondary:
        pts = []
        for j in range(SPRING_TAPS + 2):
            s = self._primary(frame - j)
            head = s.joints["head"]
            chest = s.joints["chest"]
            pelvis = s.joints["pelvis"]
            hx, hy = s.world((head.x, head.y))
            cx, cy = s.world((chest.x, chest.y))
            px, py = s.world((pelvis.x, pelvis.y))
            pts.append((hx, hy, cx, cy, px, py, head.angle * s.sign))
        sign = self._primary(frame).sign

        def acc(j, k):
            return pts[j][k] - 2 * pts[j + 1][k] + pts[j + 2][k]

        def response(k, period, zeta):
            w = math.tau / period
            wd = w * math.sqrt(1 - zeta * zeta)
            total = 0.0
            for j in range(SPRING_TAPS):
                n = j + 1
                h = math.exp(-zeta * w * n) * math.sin(wd * n) / wd
                total += h * -acc(j, k)
            return total

        head_x = response(0, 10.0, 0.32) * sign
        head_y = response(1, 9.0, 0.35)
        chest_x = response(2, 12.0, 0.4) * sign
        chest_y = response(3, 8.0, 0.45)
        pelvis_x = response(4, 11.0, 0.38) * sign
        pelvis_y = response(5, 9.0, 0.4)
        spin = response(6, 10.0, 0.35)

        def cl(v, b):
            return max(-b, min(b, v))

        return Secondary(
            beanie=cl(0.010 * head_x + 0.25 * spin, 0.10),
            pom_x=cl(0.35 * head_x, 3.5),
            pom_y=cl(0.30 * head_y, 2.5),
            strings=cl(-0.05 * chest_x, 0.5),
            hem_x=cl(0.22 * pelvis_x, 2.2),
            hem_y=cl(0.18 * pelvis_y, 1.6),
            head_drop=cl(0.18 * chest_y, 1.6),
            sleeve=cl(0.08 * chest_x, 1.0),
        )

    # -- face
    def face(self, frame: int) -> tuple[FaceState, float]:
        e = self.entry_at(frame)
        t = frame - e.start
        target = e.targets[0][1]
        prev = e.face_in
        current = blend_faces(prev, target, smoothstep(t / 8.0))
        for local, tgt in e.targets[1:]:
            if t >= local:
                current = blend_faces(current, tgt, smoothstep((t - local) / 8.0))
        face = e.clip.face(t, current)
        starts = tuple(self._blinks) + tuple(e.start + b for b in e.clip.blinks())
        blink = 0.0 if e.clip.suppress_blinks(t) else blink_amount(frame, starts)
        if blink > 0:
            face = adjust(face, eye_open=-face.eye_open * blink)
        return face, blink

    # -- public sampling
    def sample(self, frame: int) -> CharacterFrame:
        if type(frame) is not int:
            raise RenderError("frame must be an integer")
        e = self.entry_at(frame)
        sec = self.secondary(frame)
        state = evaluate(self.pose(frame), sec)
        face, blink = self.face(frame)
        return CharacterFrame(frame, e.action, state, face, blink)

    def draw(self, frame: int, stage: Stage, *, shadows: bool = True) -> tuple[DrawPath, ...]:
        cf = self.sample(frame)
        return draw_frame(cf, stage, shadows=shadows)

    def world_pelvis_x(self, frame: int) -> float:
        return self._primary(frame).pose.pelvis_x


def draw_frame(cf: CharacterFrame, stage: Stage, *, shadows: bool = True) -> tuple[DrawPath, ...]:
    placement = Placement(
        stage.frame_x(cf.state.pose.pelvis_x), stage.ground_y, stage.scale, cf.state.sign
    )
    out = contact_shadows(cf.state, placement) if shadows else ()
    return out + character_commands(cf.state, cf.face, placement)


def clamp_frame(frame: float, frames: int) -> float:
    return max(0.0, min(float(frames), frame))


class YellowMellowV2:
    """Reusable Yellow Mellow V2 character. Holds no per-frame state."""

    character_id = "yellow_mellow_v2"

    def __init__(
        self, *, start_x: float = 0.0, facing: float = 0.25, seed: str = "yellow_mellow_v2"
    ):
        finite(start_x, facing)
        if not -1 <= facing <= 1 or abs(facing) < 0.01:
            raise RenderError("facing must be in [-1, -0.01] or [0.01, 1]")
        if not isinstance(seed, str) or not seed:
            raise RenderError("seed must be a non-empty string")
        self.start_pose = standing_pose(start_x, facing)
        self.seed = seed

    @staticmethod
    def actions() -> tuple[str, ...]:
        return tuple(sorted(PRESETS)) + LOCOMOTION_ACTIONS

    def animate(
        self, requests: list[ActionRequest], *, start_expression: str = "neutral"
    ) -> Performance:
        if not requests:
            raise RenderError("Provide at least one ActionRequest")
        pose = self.start_pose
        face_end = expression(start_expression)
        current_expr = expression(start_expression)
        entries: list[Entry] = []
        frame = 0
        i = 0
        while i < len(requests):
            r = requests[i]
            if r.action in LOCOMOTION_ACTIONS:
                group = [r]
                while i + 1 < len(requests) and requests[i + 1].action in LOCOMOTION_ACTIONS:
                    i += 1
                    group.append(requests[i])
                clip, targets = self._locomotion(pose, face_end, group, current_expr)
            elif r.action in PRESETS:
                try:
                    clip = PRESETS[r.action](
                        ClipStart(pose, face_end), r.duration_frames, **dict(r.params)
                    )
                except TypeError as error:
                    raise RenderError(f"Invalid parameters for {r.action!r}: {error}") from error
                targets = ((0, expression(r.expression) if r.expression else current_expr),)
            else:
                raise RenderError(f"Unknown action {r.action!r}; use one of {self.actions()}")
            entries.append(
                Entry(
                    frame,
                    i,
                    clip,
                    face_end,
                    targets,
                    r.action if r.action not in LOCOMOTION_ACTIONS else "locomotion",
                )
            )
            current_expr = targets[-1][1]
            # Face at the end of this entry (before blinks) seeds the next entry's blend.
            temp = Performance(entries, frame + clip.duration, self.seed)
            face_end = _face_no_blink(temp, frame + clip.duration - 1)
            pose = clip.end_pose()
            frame += clip.duration
            if frame > MAX_FRAMES:
                raise RenderError("Timeline exceeds 18000 frames")
            i += 1
        return Performance(entries, frame, self.seed)

    def _locomotion(self, pose, face, group, current_expr):
        directions = {str(r.params.get("direction")) for r in group if "direction" in r.params}
        if len(directions) > 1:
            raise RenderError("Direction changes inside one locomotion sequence are not supported")
        direction = directions.pop() if directions else ("right" if pose.sign > 0 else "left")
        segments = []
        targets = []
        local = 0
        expr = current_expr
        allowed = {"direction", "speed", "stop"}
        for r in group:
            unknown = set(r.params) - allowed
            if unknown:
                raise RenderError(f"Unknown locomotion parameters {sorted(unknown)}")
            speed = float(r.params.get("speed", 1.0))
            finite(speed)
            limits = {
                "walk": (0.5, 1.4),
                "run": (0.6, 1.3),
                "start_walk": (0.5, 1.4),
                "stop": (1, 1),
            }
            lo, hi = limits[r.action]
            if r.action != "stop" and not lo <= speed <= hi:
                raise RenderError(f"{r.action} speed must be {lo}..{hi}")
            gait = "walk" if r.action == "start_walk" else r.action
            stop = bool(r.params.get("stop", False))
            segments.append(LocoSegment(gait, r.duration_frames, speed, stop, r.expression))
            if r.expression:
                expr = expression(r.expression)
            targets.append((local, expr))
            local += r.duration_frames
        clip = LocomotionClip(ClipStart(pose, face), segments, direction)
        return clip, tuple(targets)


def _face_no_blink(perf: Performance, frame: int) -> FaceState:
    e = perf.entry_at(frame)
    t = frame - e.start
    current = blend_faces(e.face_in, e.targets[0][1], smoothstep(t / 8.0))
    for local, tgt in e.targets[1:]:
        if t >= local:
            current = blend_faces(current, tgt, smoothstep((t - local) / 8.0))
    return e.clip.face(t, current)


class FollowCamera:
    """Deterministic horizontal camera: smoothed (non-causal raised-cosine) pelvis follow.

    The camera stays at ``rest_x`` while the character is near the frame anchor and eases
    into a pan only as needed; output is in logical frame units.
    """

    def __init__(
        self,
        perf: Performance,
        stage: Stage,
        *,
        anchor: float = 180.0,
        radius: int = 20,
        deadzone: float = 18.0,
    ):
        self.perf = perf
        self.stage = stage
        self.anchor = anchor
        self.radius = radius
        self.deadzone = deadzone
        raw = []
        cam = 0.0
        for f in range(perf.frames):
            x = stage.x + stage.scale * perf.world_pelvis_x(f)
            offset = x - cam - anchor
            if offset > deadzone:
                cam += offset - deadzone
            elif offset < -deadzone:
                cam += offset + deadzone
            raw.append(cam)
        self.raw = raw
        weights = [
            0.5 + 0.5 * math.cos(math.pi * k / (radius + 1)) for k in range(-radius, radius + 1)
        ]
        total = sum(weights)
        self.smooth = []
        n = len(raw)
        for f in range(n):
            acc = 0.0
            for k, w in zip(range(-radius, radius + 1), weights, strict=True):
                acc += w * raw[min(n - 1, max(0, f + k))]
            self.smooth.append(acc / total)

    def at(self, frame: int) -> float:
        return self.smooth[max(0, min(len(self.smooth) - 1, frame))]
