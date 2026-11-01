"""Verify the preserved approved audiovisual reel; no video or audio feature changes."""

import json
from pathlib import Path

from reelforge.audio.processing import mix_pcm, verify_audio
from reelforge.audio.registry import AudioRegistry
from reelforge.audio.transaction import private_directory
from reelforge.resources.monitor import JobMonitor
from reelforge.stories.contract import load_story

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "outputs/phase5a-legacy-audio"
    output.mkdir(exist_ok=True)
    story = load_story(ROOT / "examples/stories/last_farm_audio.json")
    registry = AudioRegistry(ROOT / "assets/audio")
    with JobMonitor(workspace=output) as monitor:
        with private_directory(output) as private:
            resolved = registry.resolve(
                story.audio, 360, cancelled=monitor.cancelled, workspace=private
            )
            snapshots = {r.asset.id: r.path for r in resolved}
            reference = private / "reference.f32"
            decoded = private / "decoded.f32"
            mix_pcm(resolved, 360, snapshots, reference, cancelled=monitor.cancelled)
            verification = verify_audio(
                ROOT / "artifacts/phase4a/story.mp4",
                ROOT / "artifacts/phase4b/story.mp4",
                reference,
                decoded,
                resolved,
                360,
                cancelled=monitor.cancelled,
            )
    report = {
        "scope": (
            "Preserved original 12-second AV output, freshly decoded "
            "and compared with registered frame-grid PCM"
        ),
        "verification": verification,
        "memory": monitor.report(),
        "immediate_cleanup": not private.exists(),
    }
    (ROOT / "artifacts/phase5a/legacy_audio_verification.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
