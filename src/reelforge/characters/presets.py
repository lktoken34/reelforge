"""Small experimental data contract and deterministic locomotion presets; no episode compiler."""

import math
from dataclasses import dataclass

from reelforge.rendering.model import RenderError, finite

from .contact import FootPlacement, foot_roll, plant_feet
from .rig import Joint, Pose, Rigid, Skeleton

UPPER_LEG, LOWER_LEG = 42.0, 45.0
WALK_STRIDE, RUN_STRIDE = 64.0, 164.0
WALK_CYCLE, RUN_CYCLE = 0.95, 0.60
SKELETON = Skeleton(
    (
        Joint("root", None),
        Joint("torso", "root", (0, -5)),
        Joint("neck", "torso", (0, -53)),
        Joint("head", "neck", (0, -10)),
        Joint("scarf", "neck", (-3, 4)),
        Joint("far_thigh", "root", (-7, 0)),
        Joint("far_shin", "far_thigh", (0, UPPER_LEG)),
        Joint("far_foot", "far_shin", (0, LOWER_LEG)),
        Joint("near_thigh", "root", (7, 0)),
        Joint("near_shin", "near_thigh", (0, UPPER_LEG)),
        Joint("near_foot", "near_shin", (0, LOWER_LEG)),
        Joint("far_arm", "torso", (-13, -46)),
        Joint("far_forearm", "far_arm", (0, 31)),
        Joint("far_hand", "far_forearm", (0, 29)),
        Joint("near_arm", "torso", (13, -46)),
        Joint("near_forearm", "near_arm", (0, 31)),
        Joint("near_hand", "near_forearm", (0, 29)),
    )
)
ACTIONS = ("idle", "walk", "run", "look_around", "react")
EXPRESSIONS = ("calm", "concerned", "focused", "surprised", "frightened", "determined")


@dataclass(frozen=True)
class CharacterPreset:
    character: str = "rowan_01"
    action: str = "idle"
    direction: str = "right"
    speed: float = 1.0
    expression: str = "concerned"
    intensity: float = 1.0

    def __post_init__(self):
        if self.character != "rowan_01" or self.action not in ACTIONS:
            raise RenderError("Unknown character/action; use rowan_01 and a published action")
        if self.direction not in ("left", "right") or self.expression not in EXPRESSIONS:
            raise RenderError("Use left/right and a published expression")
        finite(self.speed, self.intensity)
        if not 0.5 <= self.speed <= 1.5 or not 0.5 <= self.intensity <= 1.0:
            raise RenderError("Speed must be 0.5..1.5; intensity 0.5..1.0")

    @classmethod
    def from_data(cls, data: dict) -> "CharacterPreset":
        keys = {"character", "action", "direction", "speed", "expression", "intensity"}
        if not isinstance(data, dict) or set(data) != keys:
            raise RenderError(
                "Preset requires exactly character/action/direction/speed/expression/intensity"
            )
        if any(not isinstance(data[key], str) for key in keys - {"speed", "intensity"}):
            raise RenderError("Preset IDs must be strings")
        return cls(**data)


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def foot_target(action: str, phase: float, intensity: float = 1) -> tuple[float, float, bool]:
    """Constant backward stance velocity matches root travel; swing uses C1 easing."""
    if action not in ("walk", "run"):
        raise RenderError("Foot cycle requires walk/run")
    finite(phase, intensity)
    if not 0 <= phase < 1 or not 0.5 <= intensity <= 1:
        raise RenderError("Use normalized phase [0,1) and bounded intensity")
    stride, duty, lift = (
        (WALK_STRIDE * intensity, 0.62, 19)
        if action == "walk"
        else (RUN_STRIDE * intensity, 0.38, 31)
    )
    reach = stride * duty / 2
    if phase < duty:
        return reach - stride * phase, 0, True
    u = (phase - duty) / (1 - duty)
    # Hermite X keeps the same velocity at toe-off and heel strike as stance.
    h = u * u * (3 - 2 * u)
    x = -reach + 2 * reach * h - stride * (1 - duty) * (u * u * u - 1.5 * u * u + 0.5 * u) * 2
    return x, lift * math.sin(math.pi * u) ** 2 * (1 + 0.18 * math.sin(math.tau * u)), False


def sample_pose(preset: CharacterPreset, seconds: float, *, travel: bool = True) -> Pose:
    finite(seconds)
    if not 0 <= seconds <= 600 or type(travel) is not bool:
        raise RenderError("Time must be 0..600 seconds; travel is a boolean")
    t = seconds * preset.speed
    angles = {}
    acting = preset.action in ("look_around", "react")
    if preset.action == "idle" or acting:
        breath = math.sin(t * math.tau / 3)
        balance = -1 + 0.45 * math.sin(t * 1.2)
        height = 94.5 + 0.4 * breath * preset.intensity
        angles.update(
            torso=0.008 * breath,
            head=0.018 * math.sin(t * 1.7),
            neck=-0.006 * breath,
            scarf=0.035 * math.sin(t * 2.1 - 0.5),
        )
        for side in ("far", "near"):
            angles.update(
                {
                    side + "_arm": (0.10 if side == "far" else -0.10) + 0.015 * breath,
                    side + "_forearm": -0.16,
                    side + "_hand": 0.06 * breath,
                }
            )
        if preset.action == "look_around":
            angles.update(
                head=-0.12 * math.sin(t * 1.7) * preset.intensity,
                neck=0.035 * math.sin(t * 1.7 - 0.4),
                near_arm=-0.25,
                near_forearm=-0.65,
            )
        if preset.action == "react":
            # Finite anticipation/recoil/settle, evaluated directly from supplied time.
            recoil = smooth(t / 0.25) * (1 - 0.32 * smooth((t - 0.45) / 0.65)) * preset.intensity
            angles.update(
                torso=-0.15 * recoil,
                head=0.13 * recoil,
                near_arm=-0.72 * recoil,
                near_forearm=-1.0 * recoil,
                far_arm=0.45 * recoil,
                far_forearm=-1.2 * recoil,
                near_hand=-0.25 * recoil,
            )
            height -= 3 * recoil
            balance -= 3 * recoil
        pose = Pose(Rigid(balance, -height), tuple(angles.items()))
        return plant_feet(pose, (FootPlacement(9), FootPlacement(-9)), SKELETON)
    cycle = WALK_CYCLE if preset.action == "walk" else RUN_CYCLE
    cycles = t / cycle
    running = preset.action == "run"
    stride = (RUN_STRIDE if running else WALK_STRIDE) * preset.intensity
    balance = (1.0 if running else 1.6) * math.sin(cycles * math.tau - 0.3)
    height = (
        82.2 - 3.4 * math.cos((cycles - 0.19) * math.tau * 2)
        if running
        else 90.8 - 1.5 * math.cos(cycles * math.tau * 2)
    )
    lean = (
        0.26 + 0.04 * math.sin(cycles * math.tau * 2 - 0.3)
        if running
        else 0.045 + 0.035 * math.sin(cycles * math.tau - 0.4)
    )
    angles.update(
        torso=lean,
        neck=-0.025 * math.sin(cycles * math.tau - 0.5),
        head=-lean * 0.83 + 0.018 * math.sin(cycles * math.tau - 0.7),
        scarf=(-0.3 if running else -0.08)
        + (0.13 if running else 0.06) * math.sin(cycles * math.tau - 0.8),
    )
    distance = cycles * stride if travel else 0
    feet = []
    for side, offset, hip in (("near", 0, 7), ("far", 0.5, -7)):
        phase = (cycles + offset) % 1
        dx, lift, _ = foot_target(preset.action, phase, preset.intensity)
        pitch, pivot, state = foot_roll(phase, 0.38 if running else 0.62)
        feet.append(FootPlacement(distance + hip + dx, lift, pitch, pivot, state))
        swing = math.cos(phase * math.tau + 0.16)
        angles.update(
            {
                side + "_arm": (0.98 if running else 0.50) * swing * preset.intensity - lean * 0.35,
                side + "_forearm": (
                    -1.12 - 0.2 * math.sin(phase * math.tau - 0.4)
                    if running
                    else -0.18 - 0.22 * (0.5 - 0.5 * swing)
                ),
                side + "_hand": -0.12 * math.sin(phase * math.tau - 0.3),
            }
        )
    pose = Pose(Rigid(distance + balance, -height), tuple(angles.items()))
    return plant_feet(pose, tuple(feet), SKELETON)


def blend(a: Pose, b: Pose, weight: float) -> Pose:
    finite(weight)
    if not 0 <= weight <= 1:
        raise RenderError("Blend weight must be in [0,1]")
    aa, bb = dict(a.angles), dict(b.angles)
    return Pose(
        Rigid(
            a.root.x + (b.root.x - a.root.x) * weight,
            a.root.y + (b.root.y - a.root.y) * weight,
            a.root.angle + (b.root.angle - a.root.angle) * weight,
        ),
        tuple(
            (k, aa.get(k, 0) + (bb.get(k, 0) - aa.get(k, 0)) * weight)
            for k in sorted(aa.keys() | bb.keys())
        ),
    )


def load_preset(path) -> CharacterPreset:
    """Reuse bounded/duplicate/nonfinite JSON rejection; never validate as an episode manifest."""
    from reelforge.contracts.project import load_project

    return CharacterPreset.from_data(load_project(path))
