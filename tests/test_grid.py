"""Tests for grid operations and map generation."""

from pathlib import Path
from typer.testing import CliRunner
import h3

from hexroute.cli import app
from hexroute.grid import (
    cell_to_boundary,
    cell_to_latlng,
    generate_grid_check_map,
    get_disk,
    latlng_to_cell,
)


def test_latlng_to_cell_and_reverse() -> None:
    lat, lng = 51.5074, -0.1278
    res = 8
    cell = latlng_to_cell(lat, lng, res)
    assert isinstance(cell, str)
    assert len(cell) > 0

    center_lat, center_lng = cell_to_latlng(cell)
    # The cell center should be close to the original point
    assert abs(center_lat - lat) < 0.02
    assert abs(center_lng - lng) < 0.02


def test_cell_to_boundary() -> None:
    cell = latlng_to_cell(51.5074, -0.1278, 8)
    boundary = cell_to_boundary(cell)
    assert len(boundary) in (6, 7)  # Hexagon has 6 vertices (or 7 if closed)
    for pt in boundary:
        assert len(pt) == 2
        assert isinstance(pt[0], float)
        assert isinstance(pt[1], float)


def test_get_disk() -> None:
    cell = latlng_to_cell(51.5074, -0.1278, 8)
    disk = get_disk(cell, k=1)
    # k=1 disk in H3 has 7 cells (center + 6 neighbors)
    assert len(disk) == 7
    assert cell in disk


def test_generate_grid_check_map(tmp_path: Path) -> None:
    out_file = tmp_path / "test_map.html"
    res_path = generate_grid_check_map(
        lat=51.5074,
        lng=-0.1278,
        res=8,
        ring=1,
        out_path=out_file,
    )
    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")
    assert "html" in content.lower()
    assert "OpenStreetMap" in content or "folium" in content.lower()


def test_cli_grid_check(tmp_path: Path) -> None:
    runner = CliRunner()
    out_map = tmp_path / "cli_grid.html"
    result = runner.invoke(
        app,
        ["grid", "check", "--lat", "51.5074", "--lng", "-0.1278", "--res", "8", "--out", str(out_map)],
    )
    assert result.exit_code == 0
    assert "Grid check map generated at" in result.output
    assert out_map.exists()


def test_cli_info() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "H3 Resolution:" in result.output
