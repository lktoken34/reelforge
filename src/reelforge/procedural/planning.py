"""Stable semantic streams and immutable object plans; no drawing or native allocations."""

import hashlib
from dataclasses import dataclass

from reelforge.scenes.contract import MAX_INSTANCES, MAX_NODES, MAX_OPS, MAX_PATHS

from .contract import Request, fail

# Conservative recipe envelopes: rich detail is included, even for standard requests.
BOUNDS = {
    "sky": (40, 800),
    "backdrop": (96, 1400),
    "ground": (220, 2600),
    "distance": (200, 3000),
    "tree": (80, 2000),
    "building": (120, 1800),
    "rock": (64, 900),
    "entrance": (96, 1600),
    "foreground": (200, 5000),
    "prop": (50, 600),
}
SLOTS = (0, 2, 4, 1, 3, 5)


def sample(request: Request, identity: str, channel: str) -> float:
    key = f"environment-0.1/{request.family}/{request.seed}/{identity}/{channel}".encode()
    return min(int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / 2**64, 1 - 2**-53)


@dataclass(frozen=True)
class ObjectPlan:
    id: str
    recipe: str
    layer: str
    x: float
    y: float
    scale: float


@dataclass(frozen=True)
class Plan:
    request: Request
    horizon: float
    vanishing_x: float
    bend: float
    objects: tuple[ObjectPlan, ...]
    actor_x: float
    actor_y: float
    path_allowance: int
    operation_allowance: int
    node_allowance: int
    instance_allowance: int

    def path_x(self, y: float) -> float:
        u = (y - self.horizon) / (640 - self.horizon)
        return self.vanishing_x + (180 - self.vanishing_x) * u + self.bend * 4 * u * (1 - u)

    def half_width(self, y: float) -> float:
        u = max(0, min(1, (y - self.horizon) / (640 - self.horizon)))
        width = 7 + 45 * u * u
        return width * (1.8 if self.request.family == "settlement_street" else 1)


def plan_environment(request: Request) -> Plan:
    horizon = {"woodland_trail": 315, "settlement_street": 335, "rocky_shelter": 325}[
        request.family
    ]
    horizon += sample(request, "layout", "horizon") * 40 - 20
    vx = 180 + request.alignment * 53 + (sample(request, "layout", "vanishing") - 0.5) * 85
    bend = (sample(request, "layout", "bend") - 0.5) * 130 + request.alignment * 15
    objects = [
        ObjectPlan("sky", "sky", "sky", 0, 0, 1),
        ObjectPlan("backdrop", "backdrop", "backdrop", 0, 0, 1),
        ObjectPlan("ground", "ground", "ground", 180, 510, 1),
        ObjectPlan("distance", "distance", "distance", 0, 0, 1),
    ]
    # Fixed semantic slots, not count-dependent interpolation: density adds objects without
    # changing the position, random stream or dimensions of already selected objects.
    if request.family == "woodland_trail":
        kind = "tree"
        count = 3 + request.density
    elif request.family == "settlement_street":
        kind = "building"
        count = 2 + request.density
    else:
        kind = "rock"
        count = 2 + request.density
    for bank in ("left", "right"):
        for slot in SLOTS[:count]:
            identity = f"{kind}_{bank}_{slot}"
            y = horizon + 50 + slot * 24 + sample(request, identity, "y") * 10
            edge = 45 + slot * 5 if bank == "left" else 315 - slot * 5
            x = edge + (sample(request, identity, "x") - 0.5) * 24
            scale = 0.58 + slot * 0.105 + sample(request, identity, "scale") * 0.08
            u = (y - horizon) / (640 - horizon)
            center = vx + (180 - vx) * u + bend * 4 * u * (1 - u)
            half = (7 + 45 * u * u) * (1.8 if request.family == "settlement_street" else 1)
            clearance = 18 if kind == "tree" else 87
            x = (
                min(x, center - half - clearance)
                if bank == "left"
                else max(x, center + half + clearance)
            )
            objects.append(ObjectPlan(identity, kind, "objects", x, y, scale))
    if request.family == "rocky_shelter":
        objects.append(ObjectPlan("shelter", "entrance", "objects", vx + 22, 425, 1))
    if request.family == "woodland_trail":
        objects.append(ObjectPlan("trail_boulder", "rock", "objects", 65, 530, 0.25))
    elif request.family == "settlement_street":
        objects.extend(
            (
                ObjectPlan("street_crate", "prop", "objects", 95, 500, 1),
                ObjectPlan("street_barrel", "prop", "objects", 306, 470, 0.8),
                ObjectPlan("regrowth", "tree", "objects", 350, 475, 0.38),
            )
        )
    else:
        objects.append(ObjectPlan("dry_tree", "tree", "objects", 78, 505, 0.25))
    objects.append(ObjectPlan("foreground", "foreground", "foreground", 0, 0, 1))
    paths = sum(BOUNDS[o.recipe][0] for o in objects) + (256 if request.rowan else 0)
    ops = sum(BOUNDS[o.recipe][1] for o in objects) + (6000 if request.rowan else 0)
    instances = len(objects) + int(request.rowan)
    nodes = 8 + instances
    if paths > MAX_PATHS or ops > MAX_OPS or instances > MAX_INSTANCES or nodes > MAX_NODES:
        fail("/composition", "Expansion exceeds accepted graph budget", "ENVIRONMENT_BUDGET")
    placeholder = Plan(
        request, horizon, vx, bend, tuple(objects), 0, 525, paths, ops, nodes, instances
    )
    actor_x = placeholder.path_x(525) + (-17 if request.side == "left" else 17)
    return Plan(
        request, horizon, vx, bend, tuple(objects), actor_x, 525, paths, ops, nodes, instances
    )
