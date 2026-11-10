"""Tests for territory coverage calculation and map rendering."""

from pathlib import Path
from typer.testing import CliRunner

from hexroute.cli import app
from hexroute.coverage import (
    compute_coverage,
    densify_track,
    generate_coverage_map,
    haversine_distance,
)
from hexroute.ingest import GPSPoint

SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
 <trk>
  <name>Run</name>
  <trkseg>
   <trkpt lat="51.50740" lon="-0.12780"><time>2024-05-01T08:00:00Z</time></trkpt>
   <trkpt lat="51.52000" lon="-0.14000"><time>2024-05-01T08:10:00Z</time></trkpt>
  </trkseg>
 </trk>
</gpx>
"""


def test_haversine_distance() -> None:
    # Approx distance between (51.5074, -0.1278) and (51.5084, -0.1278) is ~111m
    d = haversine_distance(51.5074, -0.1278, 51.5084, -0.1278)
    assert 100 < d < 120


def test_densify_track() -> None:
    # 2 points separated by ~1.5 km
    p1 = GPSPoint("act1", "2024-05-01T08:00:00Z", 51.5074, -0.1278)
    p2 = GPSPoint("act1", "2024-05-01T08:10:00Z", 51.5200, -0.1400)

    densified = densify_track([p1, p2], max_step_metres=40.0)
    assert len(densified) > 20  # Should interpolate many intermediate points
    # First and last should match
    assert densified[0] == (p1.lat, p1.lng)
    assert densified[-1] == (p2.lat, p2.lng)


def test_compute_coverage() -> None:
    p1 = GPSPoint("act1", "2024-05-01T08:00:00Z", 51.5074, -0.1278)
    p2 = GPSPoint("act1", "2024-05-01T08:01:00Z", 51.5080, -0.1285)
    p3 = GPSPoint("act2", "2024-05-02T08:00:00Z", 51.5074, -0.1278)

    activities = {
        "act1": [p1, p2],
        "act2": [p3],
    }

    cov = compute_coverage(activities, res=8)
    assert len(cov) >= 1
    # The cell containing (51.5074, -0.1278) was visited by both act1 and act2
    first_cell = list(cov.keys())[0]
    assert cov[first_cell].visit_count in (1, 2)


def test_generate_coverage_map(tmp_path: Path) -> None:
    p1 = GPSPoint("act1", "2024-05-01T08:00:00Z", 51.5074, -0.1278)
    activities = {"act1": [p1]}
    cov = compute_coverage(activities, res=8)

    out_file = tmp_path / "coverage.html"
    res_path = generate_coverage_map(cov, activities=activities, out_path=out_file)
    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")
    assert "Covered Hexagons" in content


def test_cli_coverage(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    out_map = tmp_path / "coverage.html"
    data_dir.mkdir()

    (data_dir / "test_run.gpx").write_text(SAMPLE_GPX, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["coverage", "--data-dir", str(data_dir), "--cache-dir", str(cache_dir), "--out", str(out_map)],
    )
    assert result.exit_code == 0
    assert "Total unique hexes covered:" in result.output
    assert out_map.exists()
