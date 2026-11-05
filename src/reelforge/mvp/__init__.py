"""ReelForge MVP orchestration: reusable story-shot library, prompt planner and reel runner.

This package is a thin, additive orchestration layer over the existing, unchanged engine
contracts (scene-0.1, storyboard-0.1, episode-0.2, production-0.1) and the audited production
workflow. It introduces no new renderer, character rig, environment system or encoder: it only
assembles validated manifests from reusable shot presets and hands them to the existing pipeline.
"""

from .storylib import ENVIRONMENTS, SHOT_PRESETS, build_shot

__all__ = ["ENVIRONMENTS", "SHOT_PRESETS", "build_shot"]
