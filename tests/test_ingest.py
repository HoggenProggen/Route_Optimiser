"""Tests for GPX/FIT ingestion and caching."""

import gzip
from pathlib import Path
from typer.testing import CliRunner

from hexroute.cli import app
from hexroute.ingest import (
    ingest_activities,
    load_cached_ingest,
    parse_activity_file,
    parse_gpx_content,
)

SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
 <trk>
  <name>Morning Run</name>
  <type>running</type>
  <trkseg>
   <trkpt lat="51.50740" lon="-0.12780">
    <ele>15.2</ele>
    <time>2024-05-01T08:00:00Z</time>
   </trkpt>
   <trkpt lat="51.50800" lon="-0.12850">
    <ele>16.0</ele>
    <time>2024-05-01T08:01:00Z</time>
   </trkpt>
   <trkpt lat="51.50900" lon="-0.12900">
    <ele>16.5</ele>
    <time>2024-05-01T08:02:00Z</time>
   </trkpt>
  </trkseg>
 </trk>
</gpx>
"""

SAMPLE_EMPTY_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
 <trk>
  <name>Treadmill Run</name>
  <type>indoor</type>
  <trkseg>
  </trkseg>
 </trk>
</gpx>
"""


def test_parse_gpx_content() -> None:
    points = parse_gpx_content(SAMPLE_GPX, activity_id="run_1")
    assert len(points) == 3
    assert points[0].lat == 51.50740
    assert points[0].lng == -0.12780
    assert points[0].elevation == 15.2
    assert points[0].timestamp == "2024-05-01T08:00:00+00:00" or "2024-05-01T08:00:00" in points[0].timestamp


def test_parse_empty_gpx() -> None:
    points = parse_gpx_content(SAMPLE_EMPTY_GPX, activity_id="indoor_1")
    assert len(points) == 0


def test_parse_gpx_gz_file(tmp_path: Path) -> None:
    gz_file = tmp_path / "activity_123.gpx.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8") as f:
        f.write(SAMPLE_GPX)

    act_id, points, summary = parse_activity_file(gz_file)
    assert act_id == "activity_123"
    assert len(points) == 3
    assert summary.has_gps is True
    assert summary.point_count == 3


def test_ingest_directory_and_caching(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    data_dir.mkdir()

    # Write a valid GPX and an empty GPX
    (data_dir / "outdoor.gpx").write_text(SAMPLE_GPX, encoding="utf-8")
    (data_dir / "treadmill.gpx").write_text(SAMPLE_EMPTY_GPX, encoding="utf-8")

    # Ingest
    result = ingest_activities(data_dir=data_dir, cache_dir=cache_dir)
    assert result.total_files == 2
    assert result.parsed_activities == 1
    assert result.skipped_no_gps == 1
    assert result.total_points == 3
    assert "outdoor" in result.activities
    assert "treadmill" not in result.activities

    # Second load should load from cache
    cached = load_cached_ingest(cache_dir)
    assert cached is not None
    assert cached.total_files == 2
    assert cached.parsed_activities == 1
    assert cached.total_points == 3
    assert len(cached.activities["outdoor"]) == 3


def test_cli_ingest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    data_dir.mkdir()
    (data_dir / "run.gpx").write_text(SAMPLE_GPX, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["ingest", "--data-dir", str(data_dir), "--cache-dir", str(cache_dir)],
    )
    assert result.exit_code == 0
    assert "=== Ingestion Summary ===" in result.output
    assert "GPS activities parsed:  1" in result.output
    assert "Total GPS points:       3" in result.output
