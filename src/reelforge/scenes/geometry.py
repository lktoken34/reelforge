"""Sealed trusted geometry, not a scene-manifest language or executable asset plugin."""

import re
from dataclasses import dataclass

from reelforge.rendering.model import DrawPath, RenderError

from .assets import Asset, asset_by_id, cost


@dataclass(frozen=True)
class GeneratedGeometry:
    asset: Asset
    commands: tuple[DrawPath, ...]

    def __post_init__(self):
        if (
            not isinstance(self.asset.id, str)
            or re.fullmatch(r"generated_[a-z][a-z0-9_]{0,37}", self.asset.id) is None
        ):
            raise RenderError("Generated asset IDs require the private generated_ namespace")
        if self.asset.kind not in ("asset", "background", "environment") or self.asset.variants != (
            "default",
        ):
            raise RenderError("Sealed geometry supports only static default visual assets")
        if (
            type(self.asset.max_paths) is not int
            or not 1 <= self.asset.max_paths <= 4096
            or type(self.asset.max_ops) is not int
            or not 1 <= self.asset.max_ops <= 80000
        ):
            raise RenderError("Generated envelope must use bounded positive integer limits")
        if asset_by_id(self.asset.id) is not None:
            raise RenderError("Generated geometry cannot replace a registered legacy asset")
        if not isinstance(self.commands, tuple) or not 1 <= len(self.commands) <= 4096:
            raise RenderError("Generated geometry requires 1..4096 immutable commands")
        if any(not isinstance(c, DrawPath) for c in self.commands):
            raise RenderError("Only trusted DrawPath values are supported")
        paths, ops = cost(self.commands)
        if paths > self.asset.max_paths or ops > self.asset.max_ops or ops > 80000:
            raise RenderError("Generated geometry exceeds its declared envelope")
