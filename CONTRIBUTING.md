# Project conventions

Target Ubuntu 24.04 LTS / CPython 3.12, with Linux x86_64 as the first deployment target.
Other architectures/operating systems require their own native-backend evidence. Pure
foundation code may work elsewhere, but that is not deployment certification.

Use the `src/` layout, absolute package imports, UTF-8, LF newlines, four spaces and Ruff
formatting. Public functions have type hints and short purpose docstrings. Domain IDs use
lowercase ASCII snake_case and must be stable across revisions. Keep source assets and
future font licenses traceable; do not bundle the reference footage.

Project version `0.1.0` is independent of manifest version `2.0-draft1`. Draft versions may
change at review gates; changes require a new explicit ID and migration notes. Never silently
reinterpret an older manifest. Stable contracts will use semantic versioning after review.

`pyproject.toml` owns direct dependencies; `uv.lock` owns the resolved graph and hashes. Do
not manually edit the lock. Lock updates are deliberate, reviewed changes. Python patch,
Ubuntu packages, native libraries, fonts and FFmpeg builds are outside the Python lock;
record them in future reproducibility manifests. Build isolation uses a pinned backend;
CI uses `--no-isolation` with its locked build tools.

Required checks: `uv sync --frozen`, `uv run --frozen pytest`, `uv run --frozen ruff check .`,
`uv run --frozen ruff format --check .`, `uv run --frozen python -m build --no-isolation`.
Changes to packaging must also pass an installed-wheel smoke test outside the checkout.
Tests must check externally meaningful behavior, not mirror private implementation. No
visual golden tests until a rendering backend actually exists. No production media in CI.

A change description should state the problem, final behavior, checks and limitations. Keep
phase boundaries explicit. Use `feat:`, `fix:`, `docs:`, `test:` or `chore:` commit prefixes.
The local source repository is delivered for review; CI execution on GitHub is not assumed.
