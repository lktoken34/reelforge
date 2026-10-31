# Project conventions

Target Ubuntu 24.04 LTS / CPython 3.12, with Linux x86_64 as the first deployment target.
Other architectures/operating systems require their own native-backend evidence. Pure
foundation code may work elsewhere, but that is not deployment certification.

Use the `src/` layout, absolute package imports, UTF-8, LF newlines, four spaces and Ruff
formatting. Public functions have type hints and short purpose docstrings. Domain IDs use
lowercase ASCII snake_case and must be stable across revisions. Keep source assets and
future font licenses traceable; do not bundle the reference footage.

Project version `0.3.0` is independent of manifest version `2.0-draft1`. Draft versions may
change at review gates; changes require a new explicit ID and migration notes. Never silently
reinterpret an older manifest. Stable contracts will use semantic versioning after review.

`pyproject.toml` owns direct dependencies; `uv.lock` owns the resolved graph and hashes. Do
not manually edit the lock. Lock updates are deliberate, reviewed changes. Python patch,
Ubuntu packages, native libraries, fonts and FFmpeg builds are outside the Python lock;
record them in future reproducibility manifests. Build isolation uses a pinned backend;
CI uses `--no-isolation` with its locked build tools.

Required renderer checks: `uv sync --frozen --extra renderer`, `uv run --frozen --extra renderer pytest`, `uv run --frozen --extra renderer ruff check .`,
`uv run --frozen --extra renderer ruff format --check .`, `uv run --frozen --extra renderer python -m build --no-isolation`.
Changes to packaging must also pass an installed-wheel smoke test outside the checkout.
Tests must check externally meaningful behavior, not mirror private implementation. Static backend pixel/coverage and same-environment hash tests now exist; do not assume their
hashes transfer to another native stack. No production video in CI.

Also verify the base CLI without Cairo. Optional renderer build/setup is documented in
`docs/NATIVE_SETUP.md`; engineering tools do not become weak-agent commands automatically.

A change description should state the problem, final behavior, checks and limitations. Keep
phase boundaries explicit. Use `feat:`, `fix:`, `docs:`, `test:` or `chore:` commit prefixes.
The local source repository is delivered for review; CI execution on GitHub is not assumed.

Phase 2B adds real FFmpeg tests when ffmpeg/ffprobe are available; install Ubuntu `ffmpeg`
for the complete suite. Use `--basetemp outputs/test-temp` to keep test media in the workspace.
Video engineering scripts must preserve the installed foundation CLI and non-renderable manifest.
