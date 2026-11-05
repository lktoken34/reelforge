"""Prompt-to-reel MVP CLI: text prompt -> validated production -> rendered MP4.

    python3 tools/make_reel.py --prompt "..." --duration 60 --output outputs/my_reel.mp4
    python3 tools/make_reel.py --prompt "..." --duration 15 --plan-only

Pipeline: deterministic planner (reelforge.mvp.planner) -> production-0.1 manifest ->
reelforge.productions.contract.compile_production -> the audited render_production workflow
(chunked silent episode-0.2 render + verified stream-copy concat) -> final MP4. No JSON is edited
by hand between steps, no new renderer is introduced, and unsupported prompts are reported.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from threading import Event

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from reelforge.core.errors import InputError  # noqa: E402
from reelforge.mvp.planner import (  # noqa: E402
    PlanError,
    build_production_manifest,
    plan_story,
    plan_summary,
    supported,
)
from reelforge.productions.contract import compile_production  # noqa: E402

REGISTRY_ROOT = REPO / "assets" / "audio"


def main() -> int:
    parser = argparse.ArgumentParser(description="ReelForge prompt-to-reel MVP")
    parser.add_argument("--prompt", help="natural-language story prompt (supported vocabulary)")
    parser.add_argument("--duration", type=int, default=60, help="15 or 60 seconds")
    parser.add_argument("--output", default=None, help="final MP4 path")
    parser.add_argument(
        "--plan-only", action="store_true", help="plan and validate the manifest; do not render"
    )
    parser.add_argument(
        "--manifest-out", default=None, help="write the generated production manifest JSON here"
    )
    parser.add_argument(
        "--work-dir", default=None, help="render working directory (must not already exist)"
    )
    parser.add_argument("--title", default=None)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing an existing --output MP4 (default: refuse)",
    )
    parser.add_argument(
        "--list-support", action="store_true", help="print the supported vocabulary and exit"
    )
    args = parser.parse_args()

    if args.list_support:
        print(json.dumps(supported(), indent=2))
        return 0
    if not args.prompt:
        parser.error("--prompt is required (or use --list-support)")

    # 1. Prompt -> story plan -> manifest.
    try:
        plan = plan_story(args.prompt, args.duration, title=args.title)
        manifest = build_production_manifest(plan)
    except PlanError as error:
        print(json.dumps({"ok": False, "stage": "planning", "error": str(error)}, indent=2))
        return 2

    # 2. Validate through the real production contract (full scene/storyboard/direction checks).
    try:
        compiled = compile_production(manifest)
    except InputError as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "validation",
                    "error": f"{error.issue.code} at {error.issue.path}: {error.issue.message}",
                },
                indent=2,
            )
        )
        return 3

    summary = plan_summary(plan)
    summary["compiled"] = {
        "frames": compiled.frames,
        "seconds": compiled.seconds,
        "segments": len(compiled.segments),
        "chunks": len(compiled.chunks),
        "editorial_cuts": compiled.editorial_cuts,
    }
    if args.manifest_out:
        Path(args.manifest_out).write_text(json.dumps(manifest, indent=2))
    print(json.dumps(summary, indent=2))

    if args.plan_only:
        print(
            json.dumps(
                {
                    "ok": True,
                    "stage": "plan-only",
                    "frames": compiled.frames,
                    "seconds": compiled.seconds,
                },
                indent=2,
            )
        )
        return 0

    # 3. Render through the audited production workflow.
    from reelforge.productions.workflow import render_production

    output = Path(args.output).resolve() if args.output else (REPO / "outputs" / "my_reel.mp4")
    # No-clobber by default: never silently replace a completed deliverable. Fail before any
    # render so an expensive job is not started only to be undeliverable. The render workflow
    # itself keeps its own transactional no-clobber guarantee on the owned work directory.
    if (output.exists() or output.is_symlink()) and not args.overwrite:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "output",
                    "error": f"output {output} already exists; pass --overwrite to replace it, "
                    "or choose a new --output path",
                },
                indent=2,
            )
        )
        return 6
    work = (
        Path(args.work_dir).resolve() if args.work_dir else output.parent / (output.stem + "_work")
    )
    if work.exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "render",
                    "error": f"work dir {work} exists; choose a fresh --work-dir",
                }
            )
        )
        return 4
    report = render_production(compiled, work, registry_root=REGISTRY_ROOT, cancelled=Event())
    if not report.get("success"):
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "render",
                    "error": report.get("error"),
                    "report": str(work / "report.json"),
                },
                indent=2,
            )
        )
        return 5

    reel = work / "reel.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Re-check at publish time (guard against a race since the pre-render check) and publish
    # atomically via a temp file + replace, so a partial copy never corrupts an existing file.
    if (output.exists() or output.is_symlink()) and not args.overwrite:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "publish",
                    "error": f"output {output} appeared during render; pass --overwrite to "
                    "replace it. The rendered reel is preserved at " + str(reel),
                },
                indent=2,
            )
        )
        return 6
    tmp = output.with_name(output.name + ".partial")
    shutil.copy2(reel, tmp)
    tmp.replace(output)
    print(
        json.dumps(
            {
                "ok": True,
                "stage": "rendered",
                "output": str(output),
                "frames": report["frames"],
                "seconds": report["seconds"],
                "file_size_bytes": output.stat().st_size,
                "editorial_cuts": report["editorial_cuts"],
                "chunk_boundaries": report["chunk_boundaries"],
                "report": str(work / "report.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
