"""Strict geometry-0.1 validation into immutable, pre-budgeted IR."""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.rendering.model import Color, LinearGradient, Paint, Stroke
from reelforge.scenes.assets import asset_by_id
from reelforge.scenes.transforms import Placement

MAX_ASSETS, MAX_SHAPES, MAX_TOTAL_SHAPES = 8, 128, 512
MAX_ASSET_OPS, MAX_TOTAL_OPS, MAX_GROUP_DEPTH = 4096, 16000, 4
IDENTIFIER = r"[a-z][a-z0-9_]{0,23}"


def fail(path: str, message: str, code: str = "GEOMETRY_INVALID") -> None:
    raise InputError(Issue(code, path, message[:240]))


def fields(data, required: set[str], optional: set[str], path: str) -> None:
    if not isinstance(data, dict):
        fail(path, "Expected an object")
    missing, unknown = required - data.keys(), data.keys() - required - optional
    if missing or unknown:
        fail(path, f"Missing {sorted(missing)}; unsupported {sorted(unknown)}")


def number(value, low: float, high: float, path: str) -> float:
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        fail(path, f"Use a finite number in [{low}, {high}]")
    return value


def identifier(value, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(IDENTIFIER, value) is None:
        fail(path, "Use a snake_case identifier of 1..24 characters")
    return value


def vector(value, length: int, path: str, low=-512, high=512) -> tuple:
    if not isinstance(value, list) or len(value) != length:
        fail(path, f"Use an array of exactly {length} numbers")
    return tuple(number(v, low, high, f"{path}/{i}") for i, v in enumerate(value))


def placement(data, path: str, *, instance: bool = False) -> Placement:
    fields(data, {"x", "y", "scale", "rotation_degrees"}, set(), path)
    limit = 1280 if instance else 512
    return Placement(
        number(data["x"], -limit, limit, path + "/x"),
        number(data["y"], -limit, limit, path + "/y"),
        number(data["scale"], 0.25, 2, path + "/scale"),
        math.radians(number(data["rotation_degrees"], -45, 45, path + "/rotation_degrees")),
    )


@dataclass(frozen=True)
class ShapeIR:
    kind: str
    values: tuple
    fill: Paint | None
    stroke: Stroke | None
    transform: Placement
    clip: tuple | None
    operations: int


@dataclass(frozen=True)
class AssetIR:
    id: str
    size: tuple[float, float]
    anchors: tuple[tuple[str, tuple[float, float]], ...]
    shapes: tuple[ShapeIR, ...]
    operations: int


@dataclass(frozen=True)
class Document:
    assets: tuple[AssetIR, ...]


def paint(value, palette: dict, path: str) -> Paint:
    if isinstance(value, str):
        if value not in palette:
            fail(path, "Unknown palette material", "GEOMETRY_MATERIAL")
        return palette[value]
    fields(value, {"linear", "stops"}, set(), path)
    x0, y0, x1, y1 = vector(value["linear"], 4, path + "/linear")
    if (x0, y0) == (x1, y1):
        fail(path + "/linear", "Gradient endpoints must differ")
    stops = value["stops"]
    if not isinstance(stops, list) or not 2 <= len(stops) <= 8:
        fail(path + "/stops", "Use 2..8 ordered palette stops")
    result, previous = [], -1
    for i, item in enumerate(stops):
        p = f"{path}/stops/{i}"
        if not isinstance(item, list) or len(item) != 2:
            fail(p, "Use [offset, palette_id]")
        offset = number(item[0], 0, 1, p + "/0")
        if offset <= previous or not isinstance(item[1], str) or item[1] not in palette:
            fail(p, "Offsets must strictly increase; color must be a palette ID")
        result.append((offset, palette[item[1]]))
        previous = offset
    if result[0][0] != 0 or result[-1][0] != 1:
        fail(path + "/stops", "Include offsets 0 and 1")
    return LinearGradient((x0, y0), (x1, y1), tuple(result))


def path_ir(data, path: str, *, closed: bool) -> tuple:
    if not isinstance(data, list) or not 2 <= len(data) <= 128:
        fail(path, "Use 2..128 M/L/C/Z commands", "GEOMETRY_PATH")
    result, contour, contours, current = [], [], [], None
    for i, command in enumerate(data):
        p = f"{path}/{i}"
        if not isinstance(command, list) or not command or not isinstance(command[0], str):
            fail(p, "Use [command, coordinates...]", "GEOMETRY_PATH")
        kind = command[0]
        arity = {"M": 2, "L": 2, "C": 6, "Z": 0}
        if kind not in arity or len(command) != arity[kind] + 1:
            fail(p, "Supported commands: M/2, L/2, C/6, Z/0 coordinates", "GEOMETRY_PATH")
        points = tuple(number(x, -512, 512, f"{p}/{j + 1}") for j, x in enumerate(command[1:]))
        if kind == "M":
            if contour:
                if closed:
                    fail(p, "Close each filled/clip subpath before M", "GEOMETRY_PATH")
                contours.append(contour)
            current = points
            contour = [points]
        elif current is None:
            fail(p, "Each subpath starts with M; no commands after Z without M", "GEOMETRY_PATH")
        elif kind == "L":
            contour.append(points)
            current = points
        elif kind == "C":
            x0, y0 = current
            for step in range(1, 17):
                t = step / 16
                u = 1 - t
                contour.append(
                    (
                        u**3 * x0
                        + 3 * u * u * t * points[0]
                        + 3 * u * t * t * points[2]
                        + t**3 * points[4],
                        u**3 * y0
                        + 3 * u * u * t * points[1]
                        + 3 * u * t * t * points[3]
                        + t**3 * points[5],
                    )
                )
            current = points[4:]
        else:
            if closed:
                area = sum(
                    a[0] * b[1] - b[0] * a[1]
                    for a, b in zip(contour, contour[1:] + contour[:1], strict=True)
                )
                if len(contour) < 3 or abs(area) < 0.0001:
                    fail(
                        p, "Filled/clip contours require nonzero signed area", "GEOMETRY_DEGENERATE"
                    )
            contours.append(contour)
            contour, current = [], None
        result.append((kind, points))
    if contour:
        if closed:
            fail(path, "Filled and clipping paths must end each contour with Z", "GEOMETRY_PATH")
        contours.append(contour)
    if any(len(c) < 2 or max(math.dist(c[0], v) for v in c) < 0.001 for c in contours):
        fail(path, "Every contour must have nonzero extent", "GEOMETRY_DEGENERATE")
    return tuple(result)


def validate_geometry(data) -> Document:
    fields(data, {"schema_version", "palette", "assets"}, set(), "")
    if data["schema_version"] != "geometry-0.1":
        fail("/schema_version", "Use geometry-0.1")
    colors = data["palette"]
    if not isinstance(colors, dict) or not 1 <= len(colors) <= 32:
        fail("/palette", "Define 1..32 named hex colors")
    palette = {}
    for key, value in colors.items():
        identifier(key, "/palette")
        if (
            not isinstance(value, str)
            or re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value) is None
        ):
            fail("/palette/" + key, "Use #RRGGBB or #RRGGBBAA")
        palette[key] = Color(
            *(int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)),
            int(value[7:9], 16) / 255 if len(value) == 9 else 1,
        )
    records = data["assets"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_ASSETS:
        fail("/assets", "Define 1..8 assets", "GEOMETRY_BUDGET")
    assets, ids, total_shapes, total_ops = [], set(), 0, 0
    for i, record in enumerate(records):
        p = f"/assets/{i}"
        fields(record, {"id", "size", "anchors", "shapes"}, set(), p)
        identity = identifier(record["id"], p + "/id")
        if identity.startswith(("generated_", "agent_")) or asset_by_id(identity):
            fail(p + "/id", "Trusted/private asset names are reserved", "GEOMETRY_NAMESPACE")
        if identity in ids:
            fail(p + "/id", "Duplicate asset ID", "GEOMETRY_NAMESPACE")
        ids.add(identity)
        size = vector(record["size"], 2, p + "/size", 1, 512)
        anchors = record["anchors"]
        if not isinstance(anchors, dict) or not 1 <= len(anchors) <= 8 or "origin" not in anchors:
            fail(p + "/anchors", "Define 1..8 anchors including origin")
        validated_anchors = []
        for key, point in anchors.items():
            identifier(key, p + "/anchors")
            x, y = vector(point, 2, p + "/anchors/" + key, 0, 512)
            if x > size[0] or y > size[1]:
                fail(p + "/anchors/" + key, "Anchor must lie inside declared size")
            validated_anchors.append((key, (x, y)))
        shapes, entries, ops = [], 0, 0

        def visit(items, parent: Placement, depth: int, pointer: str, size=size, shapes=shapes):
            nonlocal entries, ops
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_SHAPES:
                fail(pointer, "Use 1..128 ordered shapes", "GEOMETRY_BUDGET")
            for j, shape in enumerate(items):
                q = f"{pointer}/{j}"
                entries += 1
                if entries > 128 or depth > MAX_GROUP_DEPTH:
                    fail(
                        q,
                        "Asset permits 128 total shape/group entries and group depth 4",
                        "GEOMETRY_BUDGET",
                    )
                if not isinstance(shape, dict) or shape.get("type") not in (
                    "group",
                    "rect",
                    "ellipse",
                    "polygon",
                    "path",
                ):
                    fail(q + "/type", "Choose group/rect/ellipse/polygon/path")
                kind = shape["type"]
                required = (
                    {"type", "shapes"}
                    if kind == "group"
                    else {
                        "type",
                        {"rect": "rect", "ellipse": "ellipse", "polygon": "points", "path": "path"}[
                            kind
                        ],
                    }
                )
                optional = (
                    {"transform"} if kind == "group" else {"transform", "fill", "stroke", "clip"}
                )
                fields(shape, required, optional, q)
                local = (
                    placement(shape["transform"], q + "/transform")
                    if "transform" in shape
                    else Placement()
                )
                t = parent.compose(local)
                if not 0.1 <= t.scale <= 4 or abs(t.angle) > math.pi / 2 + 1e-12:
                    fail(
                        q + "/transform",
                        "Composed scale .1..4, rotation +/-90 required",
                        "GEOMETRY_BUDGET",
                    )
                if kind == "group":
                    visit(shape["shapes"], t, depth + 1, q + "/shapes")
                    continue
                fill = (
                    paint(shape["fill"], palette, q + "/fill")
                    if shape.get("fill") is not None
                    else None
                )
                stroke = None
                if shape.get("stroke") is not None:
                    st = shape["stroke"]
                    fields(st, {"paint", "width"}, set(), q + "/stroke")
                    stroke = Stroke(
                        paint(st["paint"], palette, q + "/stroke/paint"),
                        number(st["width"], 0.25, 12, q + "/stroke/width"),
                    )
                if fill is None and stroke is None:
                    fail(q, "Provide fill and/or stroke")
                if kind in ("rect", "ellipse"):
                    values = vector(shape[kind], 4, q + "/" + kind)
                    x, y, w, h = values
                    if w < 0.01 or h < 0.01:
                        fail(
                            q + "/" + kind,
                            "Width/height (ellipse radii) must be >= .01",
                            "GEOMETRY_DEGENERATE",
                        )
                    bounds = (
                        [(x, y), (x + w, y + h)]
                        if kind == "rect"
                        else [(x - w, y - h), (x + w, y + h)]
                    )
                    bounds = [
                        (a, b) for a in {v[0] for v in bounds} for b in {v[1] for v in bounds}
                    ]
                    count = 5 if kind == "rect" else 6
                elif kind == "polygon":
                    if not isinstance(shape["points"], list) or not 3 <= len(shape["points"]) <= 64:
                        fail(q + "/points", "Use 3..64 polygon vertices", "GEOMETRY_PATH")
                    values = tuple(
                        vector(v, 2, f"{q}/points/{k}") for k, v in enumerate(shape["points"])
                    )
                    path_ir(
                        [["M", *values[0]], *[["L", *v] for v in values[1:]], ["Z"]],
                        q + "/points",
                        closed=True,
                    )
                    bounds, count = values, len(values) + 1
                else:
                    values = path_ir(shape["path"], q + "/path", closed=fill is not None)
                    bounds = [
                        points[k : k + 2] for _, points in values for k in range(0, len(points), 2)
                    ]
                    count = len(values)
                clip = (
                    path_ir(shape["clip"], q + "/clip", closed=True)
                    if shape.get("clip") is not None
                    else None
                )
                if clip:
                    bounds = [
                        *bounds,
                        *[
                            points[k : k + 2]
                            for _, points in clip
                            for k in range(0, len(points), 2)
                        ],
                    ]
                    count += len(clip)
                for x, y in bounds:
                    xx, yy = t.point(x, y)
                    if not -1e-9 <= xx <= size[0] + 1e-9 or not -1e-9 <= yy <= size[1] + 1e-9:
                        fail(
                            q,
                            "Transformed geometry/control points must fit declared size",
                            "GEOMETRY_BOUNDS",
                        )
                ops += count
                if ops > MAX_ASSET_OPS or len(shapes) + 1 > MAX_SHAPES:
                    fail(
                        q,
                        "Asset expansion exceeds 128 DrawPaths/4096 operations",
                        "GEOMETRY_BUDGET",
                    )
                shapes.append(ShapeIR(kind, values, fill, stroke, t, clip, count))

        visit(record["shapes"], Placement(), 0, p + "/shapes")
        total_shapes += len(shapes)
        total_ops += ops
        if total_shapes > MAX_TOTAL_SHAPES or total_ops > MAX_TOTAL_OPS:
            fail(p, "Document expansion exceeds 512 DrawPaths/16000 operations", "GEOMETRY_BUDGET")
        assets.append(AssetIR(identity, size, tuple(sorted(validated_anchors)), tuple(shapes), ops))
    return Document(tuple(assets))


def load_geometry(path: Path) -> Document:
    return validate_geometry(load_project(path))
