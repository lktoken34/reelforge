"""Reprocess audio against the approved silent proof; no artwork/animation rerender."""

import json
import shutil
from pathlib import Path

from render_audio_story import render_with_audio
from review_audio_story import review

from reelforge.core.errors import OperationError
from reelforge.stories.contract import load_story

ROOT = Path(__file__).resolve().parents[1]


def main():
    story = load_story(ROOT / "examples/stories/last_farm_audio.json")
    original = ROOT / "artifacts/phase4a"
    proof = ROOT / "artifacts/phase4b1/av-first"
    repeat = ROOT / "outputs/phase4b1-av-repeat"

    def silent_reference(silent, output):
        output.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(original / "story.mp4", output / "story.mp4")
        report = json.loads((original / "report.json").read_text())
        report["scope"] = "Reused approved silent reference; no fresh rendering/encoding"
        report["render_encode_seconds"] = 0.0
        report["encoded_fps"] = 0.0
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report

    outcomes = []
    for output in (proof, repeat):
        try:
            result = render_with_audio(story, output, render_silent=silent_reference)
            outcomes.append(
                {
                    "directory": str(output),
                    "success": True,
                    "wall_seconds": result["total_wall_seconds"],
                }
            )
        except (OperationError, OSError) as error:
            outcomes.append(
                {
                    "directory": str(output),
                    "success": False,
                    "code": getattr(error, "code", "IO"),
                    "message": str(error),
                }
            )
    # This is verification/reprocessing of an existing approved video, not a render benchmark.
    (ROOT / "artifacts/phase4b1/av_outcomes.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Fresh audio processing and full AV verification; archived silent video reused"
                ),
                "outcomes": outcomes,
            },
            indent=2,
        )
        + "\n"
    )
    if all(x["success"] for x in outcomes):
        summary = review(proof, repeat)
        summary["scope"] = (
            "Two successive audio reprocessing jobs in one Python process, same native build; "
            "approved silent video reused; AAC container byte identity not promised"
        )
        (proof / "repeat_consistency.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
