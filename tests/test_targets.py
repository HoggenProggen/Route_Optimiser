"""Tests for targets loading, scoring, and visualization."""

from pathlib import Path
from typer.testing import CliRunner

from hexroute.cli import app
from hexroute.grid import latlng_to_cell
from hexroute.targets import (
    HexStatus,
    expand_unclaimed_targets,
    generate_targets_map,
    load_targets_csv,
    save_targets_csv,
    score_targets,
)


def test_load_and_save_targets_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "targets.csv"
    cell1 = latlng_to_cell(51.5074, -0.1278, 8)
    cell2 = latlng_to_cell(51.5174, -0.1378, 8)

    sample_data = {
        cell1: HexStatus.ENEMY,
        cell2: HexStatus.UNCLAIMED,
    }

    save_targets_csv(sample_data, csv_file)
    assert csv_file.exists()

    loaded = load_targets_csv(csv_file)
    assert len(loaded) == 2
    assert loaded[cell1] == HexStatus.ENEMY
    assert loaded[cell2] == HexStatus.UNCLAIMED


def test_score_targets_with_adjacency() -> None:
    center = latlng_to_cell(51.5074, -0.1278, 8)
    from hexroute.grid import get_disk
    disk = list(get_disk(center, k=1))
    neighbor = disk[1] if disk[1] != center else disk[2]

    # center is "ours", neighbor is "enemy"
    targets = {
        center: HexStatus.OURS,
        neighbor: HexStatus.ENEMY,
    }

    our_territory = {center}
    scored = score_targets(targets, our_territory=our_territory)

    assert center in scored
    assert neighbor in scored

    assert scored[center].final_score == 0.0  # ours = 0.0
    assert scored[neighbor].base_score == 3.0  # enemy = 3.0
    assert scored[neighbor].adjacent_to_ours is True
    assert scored[neighbor].final_score == 3.5  # 3.0 + 0.5 bonus


def test_generate_targets_map(tmp_path: Path) -> None:
    center = latlng_to_cell(51.5074, -0.1278, 8)
    targets = {center: HexStatus.ENEMY}
    scored = score_targets(targets)

    out_file = tmp_path / "targets.html"
    res_path = generate_targets_map(scored, out_path=out_file)
    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")
    assert "Enemy Hexes" in content


def test_cli_targets_init_and_show(tmp_path: Path) -> None:
    runner = CliRunner()
    csv_file = tmp_path / "targets.csv"
    out_map = tmp_path / "targets.html"

    # 1. targets init
    init_res = runner.invoke(
        app,
        ["targets", "init", "--file", str(csv_file), "--lat", "51.5074", "--lng", "-0.1278", "--ring", "1"],
    )
    assert init_res.exit_code == 0
    assert csv_file.exists()

    # 2. targets show
    show_res = runner.invoke(
        app,
        ["targets", "show", "--file", str(csv_file), "--out", str(out_map)],
    )
    assert show_res.exit_code == 0
    assert "Scored 7 target hexes." in show_res.output
    assert out_map.exists()


def test_expand_unclaimed_targets() -> None:
    center = latlng_to_cell(51.5074, -0.1278, 8)
    existing = {center: HexStatus.OURS}

    expanded = expand_unclaimed_targets(existing, center_lat=51.5074, center_lng=-0.1278, radius_km=2.0, res=8)
    assert len(expanded) > 1
    assert expanded[center] == HexStatus.OURS
    # Surrounding hexes should be unclaimed
    unclaimed = [k for k, v in expanded.items() if v == HexStatus.UNCLAIMED]
    assert len(unclaimed) > 0
