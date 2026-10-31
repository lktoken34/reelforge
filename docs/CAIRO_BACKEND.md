# Phase 2A trusted CPU vector backend

Status: implemented engineering experiment; not part of the weak-agent episode interface.
There is no renderer CLI command, JSON-to-drawing bridge, scene compiler or production video.

## Interface and drawing semantics

`rendering/interface.py` defines structural Renderer and Surface protocols and plain PixelLayout
metadata. `rendering/model.py` defines frozen drawing values: Color, LinearGradient, PathOp,
Transform, Stroke and DrawPath. Only trusted Python constructs these values. Objects representing
Cairo surfaces, contexts, patterns and paths remain private to `backends/cairo.py`.

```python
from pathlib import Path
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.model import Color, DrawPath, rectangle

renderer = CairoRenderer(max_surface_bytes=32 * 1024 * 1024)
commands = (DrawPath(rectangle(20, 20, 120, 80), fill=Color(0.2, 0.8, 0.9, 0.6)),)
with renderer.surface(360, 640) as surface:
    renderer.draw(surface, commands, background=Color(0.03, 0.05, 0.10),
                  logical_size=(360, 640))
    surface.write_png(Path("diagnostic.png"))
# Surface is finished, pixel storage released, accounting returns to zero.
```

Methods perform these operations:

- `surface(width, height)` allocates one owned CPU image target after size/budget checks.
- `draw(target, tuple_of_DrawPath, background=..., logical_size=...)` clears the target and
  processes commands in tuple order. There is no hidden depth sort, RNG, clock or cache.
- `PathOp` supports M (move), L (line), C (cubic Bézier) and Z (close). Multiple subpaths
  are allowed. Fill and clip use the nonzero winding rule. No SVG parser or arbitrary code.
- A command may fill then stroke its path. Strokes support miter/round/bevel joins,
  butt/round/square caps and explicit miter limit. Widths are logical units.
- Transform maps local coordinates by **scale, then rotation, then translation**; positive
  rotation is clockwise on the Y-down canvas. Rotation is radians around the local origin.
  Negative scale mirrors; zero/near-singular scales are rejected. The overall logical-to-pixel
  scale follows, and can be nonuniform if the caller requests a different aspect ratio.
- The optional clip is in the same command-local coordinate system and uses the same transform.
  State is saved/restored per command, and paths are explicitly reset because Cairo paths
  are not included in its graphics-state stack.
- Color channels are straight RGBA input in [0,1]. Compositing is source-over. Clearing uses
  source replacement so reusing a surface with a transparent background removes old pixels.
  Alpha is per paint/path; group opacity and arbitrary blend modes are not implemented.
- Linear gradients have two endpoints and 2–16 strictly ordered color stops, with padded
  endpoint extension. No radial gradient, blur, lights, masks API or advanced effects.

Native-resolution gray antialiasing and 0.1 device-unit curve tolerance are explicit. There is
no supersampling, display server, GPU, font rendering or raster asset loading.

## Pixel contract and ownership

| Property | Exact behavior |
| --- | --- |
| Format | Cairo ARGB32, one native-endian 32-bit word `0xAARRGGBB` per pixel |
| Little-endian layout on this host | Bytes B, G, R, A; do not pass blindly as RGB24/RGBA |
| Big-endian layout | Bytes A, R, G, B; not exercised on current host |
| Alpha | Premultiplied native bytes; a 50% red pixel on transparent is approximately R=128,A=128 |
| Stride | Obtained from `cairo.Format.ARGB32.stride_for_width`; allocation is stride×height |
| Size limits | Integer dimensions 1–4096; all simultaneously open targets share the renderer's live-byte cap (default 32 MiB) |
| Allocation | Cairo owns the target pixel storage; no Python full-frame bytearray or shadow copy |
| Context lifetime | A short-lived context per draw; state and context references released after the call |
| Release | Use `with` or explicit idempotent `close`; finish native surface, drop backend reference, release accounting |
| Use after close | Drawing, hash, pixels, PNG write and entering again raise RenderError |
| Fallback | Destructor attempts close, but collection timing is not the lifecycle contract |

Surfaces belong to one renderer instance and cannot be passed to another. The backend is
single-threaded; counters are not a concurrent resource manager. Multiple separate renderer
instances each have their own cap, so the caller must not multiply them to evade a job budget.
Dimensions and total target bytes are checked before allocation; native failure leaves counters
unchanged. A surface held open by a caller legitimately retains its pixels. Metadata can be
read after close; native pixels cannot.

No Cairo object or borrowed raw buffer is returned by the public API. Pixel inspection returns
four integer channel values. Hashing flushes pending drawing, hashes a short layout header and
a temporary memoryview directly, then releases the view; it does not copy the whole frame.
The digest includes width/height/stride/native byte order/premultiplication, followed by all
stride×height bytes. It is not a portable PNG-file hash or a cross-platform canonical pixel hash.

## Scratch and temporary storage

There is one explicit target (0.879 MiB at 360p; 3.516 MiB at 720p), transient path/context/gradient
objects, and Cairo/pixman rasterization work. Nonrectangular antialiased clipping can allocate
native coverage/mask scratch bounded by target extents. Internal Cairo/libpng/pixman allocations
are not included in the target-only counter; measured process RSS includes them. No intermediate
full-color group surface is requested. `write_png` streams through Cairo/libpng, may allocate
native encoder scratch and performs unpremultiplication for PNG output. PNG writing is excluded
from the raster benchmark and is not a production media pipeline or atomic-write facility.

The 32 MiB cap is an explicit owned-target cap, **not a whole-process 256 MiB admission policy**.
Resource preflight for arbitrary future scenes is still unimplemented. No frame is retained by
renderer after the caller closes it, and there are no geometry/raster caches in this experiment.
Full-frame conversion, encoder queues, retained PNG bytes and copied snapshots are absent.

## Diagnostics and reproduction

Install the optional renderer as described in NATIVE_SETUP.md, then from repo root:

```bash
uv run --frozen --extra renderer python tools/render_diagnostics.py --output-dir artifacts/phase2a
uv run --frozen --extra renderer python tools/benchmark_renderer.py --frames 500 --repeats 3 --output-dir artifacts/phase2a
uv run --frozen --extra renderer pytest
```

The fixed fixture uses 121 commands, logical size 360×640, and the same scene for both sizes.
Top panel: cubic ribbon, thin lines, gradients and overlapping transparent discs.
Middle: clipped diagonal stripes, separately clipped oval, scaled/rotated overlapping cards.
Bottom: miter/round/bevel joins, alpha 0.25/0.5/0.75 over checkerboard, crisp pixel-aligned steps.
Labels are documented here to avoid introducing font/text work during a primitive milestone.
The fixtures contain no characters, environments, audio or animation timeline. Raw PNGs and
benchmark JSON are committed under artifacts/phase2a; the third-party reference is not.

## Limitations and recommendation

This is a narrowly tested software backend, not a full graphics framework. Trusted data has
basic finite/shape/size guards, but is not a sandbox for malicious Python objects. No hostile
JSON drawing interface is exposed. No grouping, nested clip stack, arbitrary blend mode,
text shaping, HDR/linear-light compositing, bitmap images, stroke dashes or animation systems.
Complex scenes can cost far more than this fixture, even within the same target size.
Native Cairo/pixman versions, hardware and float math can change coverage and hashes.

Recommend accepting Cairo for the next reviewed primitive/backend milestone based on the
measured fixture results, with target-VM and future encoder/scene-complexity gates retained.
See PHASE2A_REPORT.md for actual measurements and remaining deployment limits. Stop for
external review before Phase 2B.

Sources consulted: [Pycairo surfaces](https://pycairo.readthedocs.io/en/latest/reference/surfaces.html),
[context/state](https://pycairo.readthedocs.io/en/latest/reference/context.html), and
[Cairo image format/stride](https://cairographics.org/manual/cairo-Image-Surfaces.html).

## Phase 2B extension

The accepted drawing API remains intact. Surfaces now expose a read-only `opaque` proof flag
and `write_opaque_bgra(fd, deadline=..., cancelled=...)`, returning only a byte count.
No native buffer is returned. Compatible opaque targets can be streamed without a Python
full-frame copy; unsupported layouts/alpha are rejected. See VIDEO_PIPELINE.md for transfer
semantics and ownership. The engine still does not render agent-authored episode manifests.
