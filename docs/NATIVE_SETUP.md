# Cairo installation and dependency versions

The foundation still needs only Python 3.12 + locked JSON validation dependencies. Cairo is an
**optional engineering extra**. It is not required by the agent-facing CLI, and a default
installation does not import/install the drawing backend's native dependency.

## Standard Ubuntu 24.04 setup

On a normal Ubuntu build/development host with package-management access:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends libcairo2-dev pkg-config python3-dev build-essential
uv sync --frozen --extra renderer
uv run --frozen --extra renderer python -c 'from reelforge.rendering.backends.cairo import backend_versions; print(backend_versions())'
uv run --frozen --extra renderer pytest
```

`pyproject.toml`/`uv.lock` pin Pycairo **1.29.2**. The committed uv build setting passes
`-Dno-x11=true` to Pycairo's Meson backend, disabling Xlib/XCB surface bindings. Drawing uses
Cairo image surfaces; no display server or GPU is required. Cairo's native shared library may
still depend on distro X/font libraries; disabling binding APIs does not remove those dynamic
library dependencies. Do not edit Cairo headers to disable features.

For a pure foundation environment: `uv sync --frozen` and the three existing CLI commands work
without Cairo. Renderer-specific tests are explicitly skipped when the optional package is
absent; use `--extra renderer` for the full suite. CI contains separate foundation and Cairo jobs.
Never run default `uv sync` in an environment actively running renderer work, because it removes
unrequested extras. Use separate environments or consistently request the renderer extra.

## What was actually done in this session

Cairo runtime **1.18.0** was already present. The session's apt privilege-drop/cache setup
prevented a normal system development-package installation, so no successful system-wide
`apt-get install` is claimed. Used `apt-get download` for the official Ubuntu packages
`libcairo2-dev` (1.18.0-3build1), `pkgconf-bin` and `libpkgconf3` (1.8.1-2build1), extracted with
`dpkg-deb -x` into a workspace-only SDK, and built Pycairo against that SDK's unmodified headers
and the existing `/usr/lib/x86_64-linux-gnu/libcairo.so.2` runtime. A workspace `.pc` file described
that dynamic library/header pair without unavailable static/private/X11 development dependencies.
The Pycairo no-X11 flag was required; the initial full-binding compile correctly reported missing
XCB headers. Both unsuccessful setup attempts were corrected before any reported tests/renders.

Build environment variables pointed `PKG_CONFIG`, `PKG_CONFIG_PATH` and the SDK's `LD_LIBRARY_PATH`
to the extracted tools while building. They are not needed at runtime: the Pycairo extension
links the already-installed Cairo SONAME. The workspace SDK is an installation workaround,
not bundled source or a prerequisite on ordinary Ubuntu. Standard Ubuntu instructions above
are the recommended deployment path; they were not executed successfully in this restricted host.

## Tested native environment

| Component | Actual version |
| --- | --- |
| OS | Ubuntu 24.04.3 LTS, x86_64, glibc 2.39 |
| Python | CPython 3.12.14 |
| uv | 0.13.4 |
| Pycairo | 1.29.2, built with no-X11 |
| Cairo | 1.18.0; Ubuntu libcairo2 1.18.0-3build1 |
| pixman | Ubuntu libpixman-1-0 0.42.2-1build1 |
| libpng | Ubuntu libpng16-16t64 1.6.43-5ubuntu0.6 |
| zlib | Ubuntu zlib1g 1:1.3.dfsg-3.1ubuntu2.1 |
| Compiler used | GCC 13.3.0 |

Cairo shared-library SHA-256 in this session:
`3144bd5935aee427d6c191b6b6d0ebf9010fb6320295a7f73edd276bc6993f2d`.

The Python lock covers package distributions and hashes, not system Cairo/pixman/libpng,
compiler or isolated dependency build tools. Meson 1.12.1 was observed during this Pycairo
build; a fully pinned native build image remains future work. Reproducing byte-identical pixels
requires the native stack/architecture too. Native requirements/flags are recorded rather than
represented as pinned by `uv.lock`.

## Low-RAM deployment

Prepare a matching Linux/CPython Pycairo wheel on a roomier Ubuntu build host when possible.
Meson/Ninja compilation can use multiple cores and more memory than the ~19 MiB measured
renderer; the renderer's budget does not cover dependency builds. Keep the Cairo runtime and
its distro dependencies on the worker. Do not assume a Windows wheel bundles Linux Cairo.
Do not use another graphics binding as a silent fallback if installation fails.

Sources: [Pycairo installation](https://pycairo.readthedocs.io/en/latest/getting_started.html),
[Pycairo changelog](https://pycairo.readthedocs.io/en/latest/changelog.html), and the downloaded
Pycairo 1.29.2 `meson_options.txt` (`no-x11` option).
