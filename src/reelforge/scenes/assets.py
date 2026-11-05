"""Trusted adapters over existing components, never code/paths supplied by scene JSON."""

from dataclasses import dataclass

from reelforge.characters.presets import CharacterPreset, sample_pose
from reelforge.characters.rowan import draw_character
from reelforge.characters.secondary import preset_secondary
from reelforge.environments import artwork as art
from reelforge.environments import polish, snowy
from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath

from .transforms import Placement


@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    variants: tuple[str, ...]
    max_paths: int
    max_ops: int
    upright: bool = False
    anchor: tuple[float, float] = (0, 0)
    support_envelope: tuple[float, float, float, float] | None = None


ASSETS = (
    Asset("dusk_sky_01", "background", ("default",), 96, 2000, True),
    Asset("distant_hills_01", "background", ("default",), 128, 2000, True, (180, 350)),
    Asset(
        "orchard_ground_01",
        "environment",
        ("default",),
        384,
        6000,
        True,
        (180, 500),
        (-250, -80, 250, 250),
    ),
    Asset("barn_01", "asset", ("default",), 256, 4000),
    Asset("orchard_tree_01", "asset", ("broad", "lean", "compact", "windswept"), 64, 2000),
    Asset("fence_01", "asset", ("default",), 32, 300),
    Asset("foreground_boughs_01", "environment", ("default",), 320, 4000, False, (180, 640)),
    # Frost Peak snowy-mountain environment (Phase 9C). Code-authored vector recipes in
    # reelforge.environments.snowy; additive, no existing asset or recipe changed.
    Asset("frost_sky_01", "background", ("default",), 128, 2400, True),
    Asset("frost_peaks_01", "background", ("far", "mid"), 160, 3000, True, (180, 300)),
    Asset(
        "frost_ridge_01",
        "environment",
        ("default",),
        320,
        6000,
        True,
        (0, 0),
        (-250, -90, 250, 220),
    ),
    Asset("pine_snow_01", "asset", ("tall", "short", "cluster"), 64, 1200),
    Asset("frost_rocks_01", "asset", ("cliff", "drift"), 48, 900),
    Asset("beacon_01", "asset", ("buried", "active"), 96, 1600),
    Asset("answer_light_01", "asset", ("default",), 24, 400),
    Asset("frost_foreground_01", "environment", ("default", "storm"), 160, 3000, False, (180, 640)),
    Asset("rowan_01", "character", ("default",), 256, 6000, True),
    # Yellow Mellow V2 character asset. Its per-frame artwork is supplied by a trusted override
    # (blocking/direction), never by the static scene recipe; the envelope reserves enough
    # path/op budget for the V2 vector character plus its contact shadows.
    Asset("yellow_mellow_v2", "character", ("default",), 384, 9000, True),
)


def asset_by_id(asset_id: str) -> Asset | None:
    return next((a for a in ASSETS if a.id == asset_id), None)


def _yellow_mellow_static(character) -> tuple[DrawPath, ...]:
    """Neutral standing Yellow Mellow at the ground origin (static scene fallback)."""
    from reelforge.characters.yellow_mellow_v2.artwork import (
        Placement as YMPlacement,
    )
    from reelforge.characters.yellow_mellow_v2.artwork import (
        character_commands,
        contact_shadows,
    )
    from reelforge.characters.yellow_mellow_v2.character import CharacterFrame
    from reelforge.characters.yellow_mellow_v2.episode import DEFAULT_DRAW_SCALE, resolve_expression
    from reelforge.characters.yellow_mellow_v2.expressions import expression as ym_expression
    from reelforge.characters.yellow_mellow_v2.rig import evaluate, standing_pose

    direction = getattr(character, "direction", "right")
    sign = 1 if direction == "right" else -1
    state = evaluate(standing_pose(0.0, 0.25 * sign))
    face = ym_expression(resolve_expression(character.expression))
    cf = CharacterFrame(0, "idle", state, face, 0.0)
    placement = YMPlacement(0.0, 0.0, DEFAULT_DRAW_SCALE, sign)
    return contact_shadows(cf.state, placement) + character_commands(cf.state, cf.face, placement)


def cost(commands: tuple[DrawPath, ...]) -> tuple[int, int]:
    return len(commands), sum(len(c.path) + len(c.clip or ()) for c in commands)


def recipe(
    asset: Asset,
    variant: str,
    warmth: float,
    atmosphere: float,
    breeze: float,
    seconds: float,
    character: CharacterPreset | None,
) -> tuple[DrawPath, ...]:
    if asset.id == "dusk_sky_01":
        commands = polish.sky(warmth)
    elif asset.id == "distant_hills_01":
        commands = art.hills(atmosphere) + polish.haze(atmosphere)
    elif asset.id == "orchard_ground_01":
        commands = polish.ground(warmth)
    elif asset.id == "barn_01":
        commands = art.barn() + polish.barn_light(warmth)
    elif asset.id == "orchard_tree_01":
        seed = {"broad": 43, "lean": -15, "compact": 98, "windswept": 407}[variant]
        commands = polish.tree(seed, warmth, breeze, seconds)
    elif asset.id == "fence_01":
        commands = art.fence()
    elif asset.id == "foreground_boughs_01":
        commands = art.foreground(breeze, seconds) + polish.foreground_detail(breeze, seconds)
    elif asset.id == "frost_sky_01":
        commands = snowy.frost_sky(warmth, atmosphere)
    elif asset.id == "frost_peaks_01":
        commands = snowy.frost_peaks(variant, atmosphere)
    elif asset.id == "frost_ridge_01":
        commands = snowy.frost_ridge(warmth, atmosphere, seconds)
    elif asset.id == "pine_snow_01":
        commands = snowy.pine_snow(variant, breeze, seconds)
    elif asset.id == "frost_rocks_01":
        commands = snowy.frost_rocks(variant)
    elif asset.id == "beacon_01":
        commands = snowy.beacon(variant, warmth, seconds)
    elif asset.id == "answer_light_01":
        commands = snowy.answer_light(seconds)
    elif asset.id == "frost_foreground_01":
        commands = snowy.frost_foreground(variant, breeze, seconds)
    elif asset.id == "rowan_01" and character is not None:
        commands = (
            DrawPath(ellipse(0, 1, 19, 3), color("122c2d", 0.13)),
            DrawPath(ellipse(0, 1, 12, 1.6), color("10272a", 0.22)),
        ) + draw_character(
            sample_pose(character, seconds, travel=False),
            position=(0, 0),
            expression=character.expression,
            direction=character.direction,
            secondary=preset_secondary(character, seconds),
        )
        commands = polish.grade_character(commands, warmth, atmosphere)
    elif asset.id == "yellow_mellow_v2" and character is not None:
        # Static fallback only: a neutral standing pose at the ground origin. The episode/
        # blocking path always supplies a per-frame override instead of this recipe.
        commands = _yellow_mellow_static(character)
        commands = polish.grade_character(commands, warmth, atmosphere)
    else:
        raise ValueError("Unregistered trusted recipe or missing character preset")
    offset = Placement(-asset.anchor[0], -asset.anchor[1])
    commands = tuple(offset.command(c) for c in commands)
    paths, ops = cost(commands)
    if paths > asset.max_paths or ops > asset.max_ops:
        raise ValueError(f"Trusted recipe {asset.id} exceeds its declared complexity envelope")
    return commands
