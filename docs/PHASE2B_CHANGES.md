# Phase 2B changes

Base: approved `c70d2f2788e08b96802792c17e30ce1e0fa9cff4`.
Branch: `phase2b-streaming`; accepted branches are preserved.

## Modified

- `.github/workflows/ci.yml`
- `.gitignore`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CAIRO_BACKEND.md`
- `docs/FILE_MANIFEST.md`
- `docs/HARDWARE_CONSTRAINTS.md`
- `docs/ROADMAP.md`
- `pyproject.toml`
- `src/reelforge/__init__.py`
- `src/reelforge/core/errors.py`
- `src/reelforge/media/README.md`
- `src/reelforge/rendering/backends/cairo.py`
- `src/reelforge/rendering/interface.py`
- `src/reelforge/resources/README.md`
- `uv.lock`

## Added

- `artifacts/phase2b/benchmark_results.json`
- `artifacts/phase2b/checkpoints_360.png`
- `artifacts/phase2b/checkpoints_720.png`
- `artifacts/phase2b/diagnostic_360x640.mp4`
- `artifacts/phase2b/diagnostic_720x1280.mp4`
- `docs/PHASE2B_CHANGES.md`
- `docs/PHASE2B_HARDWARE.md`
- `docs/PHASE2B_REPORT.md`
- `docs/VIDEO_PIPELINE.md`
- `src/reelforge/core/streams.py`
- `src/reelforge/media/__init__.py`
- `src/reelforge/media/encoder.py`
- `src/reelforge/media/process.py`
- `src/reelforge/media/verify.py`
- `src/reelforge/rendering/video_diagnostic.py`
- `src/reelforge/resources/__init__.py`
- `src/reelforge/resources/monitor.py`
- `tests/test_resources.py`
- `tests/test_video_integration.py`
- `tests/test_video_pipeline.py`
- `tools/benchmark_video.py`
- `tools/render_video.py`

SDK, environments, caches, build outputs, transactions and repeat/intermediate media are excluded.
Primary MP4s, checkpoints and raw job reports are deliberate review artifacts.
