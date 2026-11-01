"""Agent-facing data only. No native renderer/media dependencies."""

from dataclasses import dataclass
from pathlib import Path

from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.scenes.contract import fields, integer, number

FAMILIES = ("woodland_trail", "settlement_street", "rocky_shelter")


def fail(path, message, code="ENVIRONMENT_INVALID"):
    raise InputError(Issue(code, path, message))


@dataclass(frozen=True)
class Request:
    title: str
    family: str
    seed: int
    density: int
    alignment: float
    structure: float
    framing: float
    detail: str
    lighting: str
    atmosphere: float
    rowan: bool
    action: str
    side: str


def validate_environment(data) -> Request:
    try:
        fields(
            data,
            {"schema_version", "title", "family", "seed", "composition", "art_direction", "rowan"},
            "",
        )
        if data["schema_version"] != "environment-0.1":
            fail("/schema_version", "Use environment-0.1")
        if data["family"] not in FAMILIES:
            fail("/family", f"Choose {FAMILIES}")
        if (
            not isinstance(data["title"], str)
            or not data["title"].strip()
            or len(data["title"]) > 120
        ):
            fail("/title", "Supply a nonempty title, at most 120 characters")
        integer(data["seed"], 0, 2**32 - 1, "/seed")
        c = data["composition"]
        fields(c, {"density", "path_alignment", "structure", "framing", "detail"}, "/composition")
        integer(c["density"], 1, 3, "/composition/density")
        number(c["path_alignment"], -1, 1, "/composition/path_alignment")
        for key in ("structure", "framing"):
            number(c[key], 0, 1, "/composition/" + key)
        if c["detail"] not in ("standard", "rich"):
            fail("/composition/detail", "Choose standard or rich")
        art = data["art_direction"]
        fields(art, {"lighting", "atmosphere"}, "/art_direction")
        if art["lighting"] not in ("dusk", "overcast"):
            fail("/art_direction/lighting", "Choose dusk or overcast")
        number(art["atmosphere"], 0, 1, "/art_direction/atmosphere")
        actor = data["rowan"]
        fields(actor, {"enabled", "action", "side"}, "/rowan")
        if type(actor["enabled"]) is not bool:
            fail("/rowan/enabled", "Use a boolean")
        if actor["action"] not in ("idle", "look_around", "react"):
            fail("/rowan/action", "Use idle/look_around/react")
        if actor["side"] not in ("left", "right"):
            fail("/rowan/side", "Choose left or right")
    except InputError as error:
        if error.issue.code == "SCENE_INVALID":
            fail(error.issue.path, error.issue.message)
        raise
    return Request(
        data["title"],
        data["family"],
        data["seed"],
        c["density"],
        c["path_alignment"],
        c["structure"],
        c["framing"],
        c["detail"],
        art["lighting"],
        art["atmosphere"],
        actor["enabled"],
        actor["action"],
        actor["side"],
    )


def load_environment(path: Path) -> Request:
    return validate_environment(load_project(Path(path)))
