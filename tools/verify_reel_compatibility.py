"""Reuse accepted pixel evidence and reverify original 12-second AV without rerendering."""

import hashlib
import json
from pathlib import Path

from reelforge.audio.processing import mix_pcm, verify_audio
from reelforge.audio.registry import AudioRegistry
from reelforge.audio.transaction import private_directory
from reelforge.core.errors import OperationError
from reelforge.media.verify import verify_video
from reelforge.resources.monitor import JobMonitor
from reelforge.stories.contract import load_story

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase7b"


def main():
    work = ROOT / "outputs/phase7b-legacy-compatibility"
    work.mkdir(exist_ok=False)
    evidence = ROOT / "artifacts/phase7a/compatibility_and_decode.json"
    historical = json.loads(evidence.read_text())
    report = {
        "historical_evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "historical_594_checkpoint_pass": historical["all_594_legacy_pixels_preserved"],
        "scope": (
            "594 accepted checkpoints reused as historical evidence; "
            "original evaluators unchanged; no 594-frame rerender"
        ),
        "legacy_av": None,
        "error": None,
    }
    private = None
    try:
        with JobMonitor(workspace=work) as monitor:
            audio = load_story(ROOT / "examples/stories/last_farm_audio.json")
            registry = AudioRegistry(ROOT / "assets/audio")
            with private_directory(work) as private:
                cues = registry.resolve(
                    audio.audio, 360, cancelled=monitor.cancelled, workspace=private
                )
                pcm, decoded = private / "reference.f32", private / "decoded.f32"
                mix_pcm(
                    cues, 360, {r.asset.id: r.path for r in cues}, pcm, cancelled=monitor.cancelled
                )
                report["legacy_av"] = verify_audio(
                    ROOT / "artifacts/phase4a/story.mp4",
                    ROOT / "artifacts/phase4b/story.mp4",
                    pcm,
                    decoded,
                    cues,
                    360,
                    cancelled=monitor.cancelled,
                )
                report["legacy_video"] = verify_video(
                    ROOT / "artifacts/phase4b/story.mp4",
                    width=720,
                    height=1280,
                    frames=360,
                    cancelled=monitor.cancelled,
                )
    except (OperationError, OSError) as error:
        report["error"] = {"code": getattr(error, "code", "LEGACY_RUNTIME"), "message": str(error)}
    report["transaction_clean_at_return"] = private is not None and not private.exists()
    (OUT / "legacy_compatibility.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["error"] is None and report["transaction_clean_at_return"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
