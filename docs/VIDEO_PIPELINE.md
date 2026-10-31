# Phase 2B — bounded CPU video pipeline

Status: trusted engineering interface only. The installed capabilities/schema/validate CLI
and `2.0-draft1` manifests are unchanged and still not render-ready. No story compiler,
character/rig, catalog, general timeline, text, lighting system, audio or artistic QA is added.

## Boundaries

- `rendering/video_diagnostic.py`: one pure frame-index-to-geometry fixture, extending existing
  primitives. No stateful clock, random streams or generic timeline.
- `Surface.write_opaque_bgra(fd, deadline=..., cancelled=...)`: narrowly scoped synchronous raw
  transfer. Returns only the byte count. No memoryview, callback, buffer token or frame queue
  is exported. Cairo-specific data stays inside the backend.
- `core/streams.py`: POSIX nonblocking write loop, deadline/cancellation checks and stable error
  categories. It has no knowledge of FFmpeg or rendering.
- `media/encoder.py`: one-use FFmpeg transaction, byte/layout validation, lifecycle and publication.
  No Cairo imports. `media/process.py` handles bounded technical subprocesses and process groups.
- `media/verify.py`: metadata, full decode/checksums and bounded MP4 header checks. No art scoring.
- `resources/monitor.py`: Linux preflight and sampled worker-plus-descendants RSS. No media dependency.
- `tools/render_video.py`: one trusted 150-frame render/verify job. `tools/benchmark_video.py`
  launches four fresh jobs and compares decoded content. Neither is an installed agent command.

## Raw pixel and ownership contract

The sole initial transport is tightly packed **BGRA8**, 30 fps, 360×640 or 720×1280. It is allowed
only on a **little-endian** platform where the native surface metadata reports premultiplied
ARGB32, four-byte pixels and exactly width×4 stride. Cairo's native word `0xAARRGGBB` then appears
as B,G,R,A bytes. Big-endian, another format, mismatched dimensions and padded strides are rejected;
there is no silent swizzle, conversion backend or codec fallback.

Premultiplied values may be sent this way only for **opaque** frames. A successful `draw` marks
an owned surface opaque only when its cleared background alpha is exactly 1. All supported
subsequent paints use source-over, so global opacity is preserved even for translucent objects
and antialiased edges. Fresh, closed, transparent-background and failed-draw surfaces are not
proven opaque. A transparent-background image completely covered by opaque shapes is conservatively
rejected as well. This avoids dark edges from treating translucent premultiplied pixels as straight
alpha. No unpremultiplication/conversion full-frame copy is needed for the accepted case.

The Cairo method flushes drawing, obtains a **private** memoryview, synchronously consumes it via
nonblocking `os.write` slices of at most 64 KiB, releases every slice, then releases the root view
in `finally`. The only consumer of a slice is the OS write syscall. No Python caller or encoder
object receives it; it cannot be queued or retained by a callback. The method checks a finite
absolute monotonic deadline, cancellation and nonblocking descriptor mode. Partial writes are
counted accurately. Broken pipe, zero progress, timeout and cancellation interrupt the transfer.
Kernel pipe copies and FFmpeg's own decode/conversion buffers remain; this is elimination of
unnecessary Python full-frame copies, not a claim of kernel zero-copy.

One caller-owned surface is reused sequentially for the clip and closed before encoder finalization.
The encoder does not own or close it. A failed encoder leaves an open caller-owned surface usable;
a surrounding `with` still releases it on exceptions. Per-frame byte count is exactly 921600 or
3686400. The encoder validates frame count before publication and rejects too few/many frames.
No PNG is written between Cairo and FFmpeg. Review PNGs are extracted from completed MP4s afterward.
The inherited 32 MiB owned-target cap remains separate from whole-job memory policy.

## FFmpeg command

The exact command array and ephemeral workspace output path are in every raw job report. At 720p:

```bash
ffmpeg -hide_banner -loglevel error -nostats -nostdin \
  -max_alloc 67108864 -threads 1 -filter_threads 1 -filter_complex_threads 1 \
  -f rawvideo -pixel_format bgra -video_size 720x1280 -framerate 30 -i pipe:0 \
  -an -sn -dn -frames:v 150 -c:v libx264 -preset veryfast -tune zerolatency \
  -threads:v 1 \
  -x264-params threads=1:lookahead_threads=1:sync-lookahead=0:rc-lookahead=0:bframes=0:ref=1 \
  -profile:v main -level:v 3.1 -crf 20 \
  -vf scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p \
  -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -color_range tv -tag:v avc1 -movflags +faststart -f mp4 -n WORKSPACE_PENDING.mp4
```

Arguments are a Python list with `shell=False`; no manifest text enters them. Input/codec/filter
thread settings are explicit. libx264 lookahead, B-frames and reference buffering are restrained;
no GPU codec is selected. `-max_alloc` is a **per-FFmpeg-allocation guard**, not a process RSS cap,
and does not control every allocation in external libraries. Whole-job soft monitoring is separate.

The output is silent H.264 Main level 3.1, avc1-tagged yuv420p in MP4, with moov before mdat.
That is a browser-compatible format target; an actual browser playback test is not claimed.
RGB-to-limited-range BT.709 YUV conversion is explicit. This is not full color management or an
HDR/linear-light system, and chroma subsampling/lossy compression can soften colored edges.

## Process and output lifecycle

1. Validate size/container/count/timeouts; check FFmpeg executable and libx264 availability.
   There is no fallback codec. The job driver performs conservative memory preflight first.
2. Create `.reelforge-encode-*` under the destination's **existing parent directory**, not `/tmp`.
   The pending MP4 does not exist initially; FFmpeg uses `-n`.
3. Start a new process session with unbuffered stdin, stdout discarded, stderr continuously
   drained by a dedicated thread into a 16 KiB tail. This avoids stderr-pipe deadlock and
   unbounded retained logs. All writes use backpressure rather than a frame queue.
4. Each transfer has the lesser of the global job deadline (default 60s) and a per-frame deadline
   (default 5s). Waiting for EOF completion polls cancellation/deadline too. Renderer draw calls
   themselves are not asynchronously preemptible; this small trusted fixture completes quickly.
5. Close stdin after the exact declared frame count. Require child exit 0 and a nonempty output.
   Flush the pending file with fsync, then publish in the same filesystem. Default publication
   uses an atomic hard link, preventing a no-clobber race; explicit `overwrite=True` uses atomic
   replace. Existing output remains untouched on failures before publication. Hard-link/rename
   support is required; failures are reported, never replaced with non-atomic copying.
6. Abort on exceptions, cancellation or KeyboardInterrupt: SIGTERM the owned process group,
   wait at most 0.5s, SIGKILL remaining group members, reap with a finite timeout, close pipes,
   join stderr reader and remove the private directory. No encoder destructor is relied upon.

Publication follows successful encoding, not successful artistic review. The trusted job driver
then performs technical verification. A later verification failure is explicit and can leave the
completed encoded file for diagnosis; it does not silently certify or publish a production episode.
Filesystem failure can prevent cleanup itself; such errors are surfaced. Power-loss durability
of the containing directory and hostile executable behavior are outside this milestone.

## Memory policy

See PHASE2B_HARDWARE.md. The default driver requires at least 256 MiB job headroom + 64 MiB reserve
in the minimum of host MemAvailable and cgroup remaining capacity. Unknown capacity is rejected.
A 10ms-nominal sampler sums renderer and descendant RSS at the same observation, records encoder
RSS separately, and requests cooperative cancellation above the 256 MiB budget or below the reserve.
This is not an OS-enforced cgroup limit or an OOM guarantee; sampling/allocations race. No shared
cgroup limits or host swap configuration are modified. Dependency builds are outside runtime budgets.

## Verification and repeatability

`verify_video` runs bounded ffprobe with `-count_frames`, requiring requested dimensions, h264,
avc1, yuv420p, 30 fps, duration within one frame and exact decoded frame count. A full FFmpeg
`-xerror -err_detect explode` decode generates SHA-256 hashes for every RGB24 frame. Return code,
error output, hash count and changing decoded frames are checked. MP4 top-level headers are read
with bounded seeks to verify ftyp and faststart box order; the entire MP4 is never read into Python.

Two independent encodes per resolution must produce the same 150 decoded RGB hashes on the same
native stack. This does not require byte-identical MP4s or promise cross-FFmpeg-build equality.
Pure source geometry is also checked out of order and at first/middle/last checkpoints. Contact
sheets show frames 0,75,149 from left to right; visually inspected behavior is documented in the report.

## Installation/reproduction

On Ubuntu 24.04, with Python 3.12 and uv:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg libcairo2-dev pkg-config python3-dev build-essential
uv sync --frozen --extra renderer
mkdir -p outputs/phase2b
uv run --frozen --extra renderer python tools/render_video.py \
  --width 720 --output outputs/phase2b/demo.mp4 --report outputs/phase2b/demo.json
uv run --frozen --extra renderer pytest --basetemp outputs/test-temp
```

For four independent measured jobs and repeat comparisons, run `tools/benchmark_video.py` with
`--output-dir outputs/phase2b-reviewed --scratch-dir outputs/phase2b-repeats-new`. Use fresh output
paths: default no-clobber behavior is deliberate. Existing committed artifacts must not be
silently overwritten. For native wheel/build constraints see NATIVE_SETUP.md. If `/tmp` is small,
create a workspace build directory and set TMPDIR there for dependency installation; encoding
already uses explicit destination-adjacent storage and does not depend on TMPDIR.

FFmpeg 6.1.1/libx264 and Pycairo 1.29.2/Cairo 1.18.0 were tested here. Full build/native versions
and raw reports are retained; portable native-build pinning is still future work.

Sources consulted: [FFmpeg rawvideo formats](https://ffmpeg.org/ffmpeg-formats.html#rawvideo),
[codec/libx264 options](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb), and
[general options](https://ffmpeg.org/ffmpeg.html). No model or network calls occur during rendering.

Cleanup hardening explicitly unlinks the known pending file before directory removal. The batch
launcher checks/reconciles only each reaped worker's validated destination-adjacent transaction
path. It does not scan/delete unknown active jobs. Abrupt external SIGKILL/host interruption has
no automatic stale-directory scavenger. Transaction directories are ignored by Git.
