"""production-0.1: a higher-level plan that renders a long silent reel from accepted episodes.

A production is an ordered list of accepted silent episode-0.2 chunks (each 1..10 ninety-frame
segments). It does not introduce a new renderer, character rig, encoder or resource model: each
chunk is rendered by the existing audited episode workflow, and the chunk MP4s are joined with an
FFmpeg stream-copy concat (no re-encode). Historical contracts and their bounds are unchanged.
"""

from .contract import (
    Production,
    ProductionChunk,
    compile_production,
    load_production,
)

__all__ = [
    "Production",
    "ProductionChunk",
    "compile_production",
    "load_production",
]
