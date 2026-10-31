"""Observable pixel/state/lifetime behavior of the optional trusted-code backend."""

import math
from pathlib import Path

import pytest

pytest.importorskip("cairo")

from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import BACKGROUND, LOGICAL_SIZE, diagnostic_commands, ellipse
from reelforge.rendering.interface import Renderer
from reelforge.rendering.model import (
    Color,
    DrawPath,
    LinearGradient,
    PathOp,
    RenderError,
    Stroke,
    SurfaceBudgetError,
    Transform,
    rectangle,
)

CLEAR = Color(0, 0, 0, 0)
RED, BLUE = Color(1, 0, 0), Color(0, 0, 1)


def draw(renderer, surface, commands, background=CLEAR, logical_size=(16, 16)):
    renderer.draw(surface, tuple(commands), background=background, logical_size=logical_size)


def test_alpha_over_transparent_is_premultiplied():
    renderer: Renderer = CairoRenderer()
    with renderer.surface(16, 16) as surface:
        draw(renderer, surface, [DrawPath(rectangle(0, 0, 16, 16), Color(1, 0, 0, 0.5))])
        assert surface.pixel_rgba8_premultiplied(8, 8) == (128, 0, 0, 128)
        assert surface.layout.premultiplied is True
        assert surface.layout.stride >= 16 * 4
        assert surface.layout.size_bytes == surface.layout.stride * 16


def test_alpha_over_opaque_and_background_clear_on_reuse():
    renderer = CairoRenderer()
    with renderer.surface(16, 16) as surface:
        draw(renderer, surface, [DrawPath(rectangle(0, 0, 16, 16), Color(1, 0, 0, 0.5))], BLUE)
        assert surface.pixel_rgba8_premultiplied(8, 8) == (128, 0, 127, 255)
        draw(renderer, surface, [])
        assert surface.pixel_rgba8_premultiplied(8, 8) == (0, 0, 0, 0)


def test_clip_contains_fill_and_does_not_leak_to_next_command():
    renderer = CairoRenderer()
    with renderer.surface(16, 16) as surface:
        draw(
            renderer,
            surface,
            [
                DrawPath(rectangle(0, 0, 16, 16), RED, clip=rectangle(2, 2, 4, 4)),
                DrawPath(rectangle(10, 10, 2, 2), BLUE),
            ],
        )
        assert surface.pixel_rgba8_premultiplied(3, 3) == (255, 0, 0, 255)
        assert surface.pixel_rgba8_premultiplied(1, 1) == (0, 0, 0, 0)
        assert surface.pixel_rgba8_premultiplied(11, 11) == (0, 0, 255, 255)
        assert surface.pixel_rgba8_premultiplied(7, 3) == (0, 0, 0, 0)


def test_translation_rotation_scale_order_and_state_isolation():
    renderer = CairoRenderer()
    with renderer.surface(16, 16) as surface:
        draw(
            renderer,
            surface,
            [
                DrawPath(rectangle(0, 0, 2, 2), RED, transform=Transform(8, 3, math.pi / 2, 2, 1)),
                DrawPath(rectangle(0, 0, 1, 1), BLUE),
            ],
        )
        assert surface.pixel_rgba8_premultiplied(6, 4) == (255, 0, 0, 255)
        assert surface.pixel_rgba8_premultiplied(0, 0) == (0, 0, 255, 255)
        assert surface.pixel_rgba8_premultiplied(4, 4) == (0, 0, 0, 0)


def test_logical_resolution_mapping():
    renderer = CairoRenderer()
    with renderer.surface(32, 32) as surface:
        draw(renderer, surface, [DrawPath(rectangle(2, 2, 2, 2), RED)])
        assert surface.pixel_rgba8_premultiplied(5, 5) == (255, 0, 0, 255)
        assert surface.pixel_rgba8_premultiplied(2, 2) == (0, 0, 0, 0)


def test_painter_order_is_explicit():
    renderer = CairoRenderer()
    red = DrawPath(rectangle(0, 0, 16, 16), RED)
    blue = DrawPath(rectangle(4, 4, 8, 8), BLUE)
    with renderer.surface(16, 16) as surface:
        draw(renderer, surface, [red, blue])
        first = surface.pixel_sha256()
        assert surface.pixel_rgba8_premultiplied(8, 8) == (0, 0, 255, 255)
        draw(renderer, surface, [blue, red])
        assert surface.pixel_rgba8_premultiplied(8, 8) == (255, 0, 0, 255)
        assert surface.pixel_sha256() != first


def test_curve_has_antialiased_edge_and_filled_center():
    renderer = CairoRenderer()
    with renderer.surface(16, 16) as surface:
        draw(renderer, surface, [DrawPath(ellipse(8, 8, 5.5, 5.5), RED)])
        assert surface.pixel_rgba8_premultiplied(8, 8) == (255, 0, 0, 255)
        assert surface.pixel_rgba8_premultiplied(1, 1) == (0, 0, 0, 0)
        assert 0 < surface.pixel_rgba8_premultiplied(13, 8)[3] < 255


def test_linear_gradient_and_transparency():
    renderer = CairoRenderer()
    gradient = LinearGradient((0, 0), (16, 0), ((0, RED), (1, Color(0, 0, 1, 0.5))))
    with renderer.surface(16, 16) as surface:
        draw(renderer, surface, [DrawPath(rectangle(0, 0, 16, 16), gradient)])
        left, right = (surface.pixel_rgba8_premultiplied(x, 8) for x in (0, 15))
        assert left[0] > right[0]
        assert right[2] > left[2]
        assert 120 < right[3] < left[3] <= 255


def test_stroke_joins_produce_distinct_coverage():
    renderer = CairoRenderer()
    path = (PathOp("M", (3, 13)), PathOp("L", (8, 3)), PathOp("L", (13, 13)))
    hashes = set()
    with renderer.surface(16, 16) as surface:
        for join in ("miter", "round", "bevel"):
            draw(renderer, surface, [DrawPath(path, stroke=Stroke(RED, 4, join, "butt"))])
            hashes.add(surface.pixel_sha256())
    assert len(hashes) == 3


def test_live_surface_budget_reclaimed_even_when_exception_escapes():
    renderer = CairoRenderer(max_surface_bytes=16 * 16 * 4)
    with pytest.raises(RuntimeError, match="fixture failure"):
        with renderer.surface(16, 16) as surface:
            assert renderer.active_surfaces == 1
            with pytest.raises(SurfaceBudgetError):
                renderer.surface(1, 1)
            raise RuntimeError("fixture failure")
    assert surface.closed
    assert renderer.allocated_bytes == renderer.active_surfaces == 0
    surface.close()  # Idempotent, counters must not become negative.
    with renderer.surface(16, 16):
        pass
    assert renderer.allocated_bytes == renderer.active_surfaces == 0


def test_rejected_draw_and_all_closed_operations():
    renderer = CairoRenderer()
    with renderer.surface(16, 16) as surface:
        with pytest.raises(RenderError):
            draw(renderer, surface, [{"execute": "anything"}])
    for operation in (
        surface.pixel_sha256,
        lambda: surface.write_png(Path("unused.png")),
        lambda: surface.pixel_rgba8_premultiplied(0, 0),
        lambda: draw(renderer, surface, []),
        surface.__enter__,
    ):
        with pytest.raises(RenderError, match="closed"):
            operation()
    assert renderer.active_surfaces == 0


def test_foreign_surface_cannot_be_drawn():
    owner, other = CairoRenderer(), CairoRenderer()
    with owner.surface(16, 16) as surface:
        with pytest.raises(RenderError, match="belong"):
            draw(other, surface, [])


@pytest.mark.parametrize("dimensions", [(0, 5), (5, -1), (4097, 1), (True, 1), (2.5, 2)])
def test_bad_dimensions_are_rejected_without_allocation(dimensions):
    renderer = CairoRenderer()
    with pytest.raises(SurfaceBudgetError):
        renderer.surface(*dimensions)
    assert renderer.allocated_bytes == renderer.active_surfaces == 0


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Color(float("inf"), 0, 0),
        lambda: Transform(sx=0),
        lambda: PathOp("C", (0, 0)),
        lambda: Stroke(RED, -1),
        lambda: LinearGradient((0, 0), (0, 0), ((0, RED), (1, BLUE))),
    ],
)
def test_invalid_trusted_values_fail_clearly(factory):
    with pytest.raises(RenderError):
        factory()


def test_same_fixture_is_deterministic_across_allocation_and_reuse(tmp_path):
    renderer = CairoRenderer()
    commands = diagnostic_commands()
    hashes = []
    for _ in range(3):
        with renderer.surface(360, 640) as surface:
            renderer.draw(surface, commands, background=BACKGROUND, logical_size=LOGICAL_SIZE)
            hashes.append(surface.pixel_sha256())
            renderer.draw(surface, commands, background=BACKGROUND, logical_size=LOGICAL_SIZE)
            assert surface.pixel_sha256() == hashes[-1]
            output = tmp_path / "diagnostic.png"
            surface.write_png(output)
            assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert len(set(hashes)) == 1
    assert renderer.allocated_bytes == renderer.active_surfaces == 0


def test_large_surface_rejected_by_bytes_not_only_dimension_limit():
    renderer = CairoRenderer()
    with pytest.raises(SurfaceBudgetError, match="byte budget"):
        renderer.surface(4096, 4096)
    assert renderer.allocated_bytes == renderer.active_surfaces == 0


def test_png_io_failure_still_releases_target(tmp_path):
    renderer = CairoRenderer()
    with pytest.raises(OSError):
        with renderer.surface(16, 16) as surface:
            surface.write_png(tmp_path / "missing" / "file.png")
    assert surface.closed
    assert renderer.allocated_bytes == renderer.active_surfaces == 0
