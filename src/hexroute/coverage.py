"""Coverage mapping and track densification for H3 territory visualization."""

from collections import defaultdict
from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Sequence
import folium
from folium.plugins import Fullscreen

from hexroute.grid import cell_to_boundary, cell_to_latlng, latlng_to_cell
from hexroute.ingest import GPSPoint

# Approximate metres per degree at equator
METRES_PER_DEG_LAT = 111_139.0


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in metres between two points using haversine formula."""
    r = 6371000.0  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def densify_track(
    points: Sequence[GPSPoint],
    max_step_metres: float = 40.0,
) -> list[tuple[float, float]]:
    """
    Interpolate points along a GPS track so consecutive points are no more than
    max_step_metres apart. This prevents skipping H3 cells on fast or sparse segments.
    """
    if not points:
        return []

    densified: list[tuple[float, float]] = [(points[0].lat, points[0].lng)]

    for i in range(1, len(points)):
        p1 = points[i - 1]
        p2 = points[i]

        dist = haversine_distance(p1.lat, p1.lng, p2.lat, p2.lng)
        if dist > max_step_metres and dist < 50_000.0:  # Skip unrealistic GPS jumps > 50km
            num_steps = math.ceil(dist / max_step_metres)
            for step in range(1, num_steps):
                frac = step / num_steps
                interp_lat = p1.lat + frac * (p2.lat - p1.lat)
                interp_lng = p1.lng + frac * (p2.lng - p1.lng)
                densified.append((interp_lat, interp_lng))

        densified.append((p2.lat, p2.lng))

    return densified


@dataclass
class HexCoverage:
    cell: str
    visit_count: int = 0
    last_visit: str | None = None
    activity_ids: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "visit_count": self.visit_count,
            "last_visit": self.last_visit,
            "activity_ids": sorted(self.activity_ids),
        }


def compute_coverage(
    activities: dict[str, list[GPSPoint]],
    res: int = 8,
    max_step_metres: float = 40.0,
) -> dict[str, HexCoverage]:
    """
    Calculate H3 cell coverage across all activities.
    Each activity visiting a cell increments its visit count once.
    """
    coverage_map: dict[str, HexCoverage] = {}

    for act_id, points in activities.items():
        if not points:
            continue

        densified_coords = densify_track(points, max_step_metres=max_step_metres)
        visited_cells: set[str] = set()

        for lat, lng in densified_coords:
            cell = latlng_to_cell(lat, lng, res)
            visited_cells.add(cell)

        # Get latest timestamp for this activity
        act_timestamps = [p.timestamp for p in points if p.timestamp]
        act_last_time = max(act_timestamps) if act_timestamps else None

        for cell in visited_cells:
            if cell not in coverage_map:
                coverage_map[cell] = HexCoverage(cell=cell)

            rec = coverage_map[cell]
            rec.visit_count += 1
            rec.activity_ids.add(act_id)

            if act_last_time:
                if rec.last_visit is None or act_last_time > rec.last_visit:
                    rec.last_visit = act_last_time

    return coverage_map


def _get_coverage_color(visit_count: int, max_visits: int) -> tuple[str, float]:
    """Determine hex fill color and opacity based on visit count."""
    if visit_count <= 1:
        return "#4575b4", 0.35  # Blue
    elif visit_count == 2:
        return "#74add1", 0.45  # Light blue
    elif visit_count <= 4:
        return "#fdae61", 0.55  # Orange
    elif visit_count <= 8:
        return "#f46d43", 0.65  # Coral
    else:
        return "#d73027", 0.75  # Deep Red


def generate_coverage_map(
    coverage: dict[str, HexCoverage],
    activities: dict[str, list[GPSPoint]] | None = None,
    out_path: str | Path = "out/coverage.html",
    home_lat: float | None = None,
    home_lng: float | None = None,
) -> Path:
    """
    Generate an interactive Folium coverage map with shaded H3 hexagons
    and an optional toggle for raw GPS tracks.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Determine center location
    if home_lat is not None and home_lng is not None:
        center_lat, center_lng = home_lat, home_lng
    elif coverage:
        # Average center of all covered cells
        lats = [cell_to_latlng(c)[0] for c in coverage.keys()]
        lngs = [cell_to_latlng(c)[1] for c in coverage.keys()]
        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)
    else:
        center_lat, center_lng = 51.5074, -0.1278

    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    Fullscreen().add_to(m)

    hex_group = folium.FeatureGroup(name=f"Covered Hexagons ({len(coverage)})", show=True)
    max_visits = max((c.visit_count for c in coverage.values()), default=1)

    for cell, rec in coverage.items():
        boundary = cell_to_boundary(cell)
        poly_coords = [[p[0], p[1]] for p in boundary]
        color, opacity = _get_coverage_color(rec.visit_count, max_visits)
        c_lat, c_lng = cell_to_latlng(cell)

        last_vis_str = rec.last_visit[:10] if rec.last_visit else "Unknown"
        popup_html = (
            f"<div style='font-family: sans-serif; font-size: 13px;'>"
            f"<b>H3 Hex:</b> <code>{cell}</code><br>"
            f"<b>Visits:</b> <span style='color: #d73027; font-weight: bold;'>{rec.visit_count}</span><br>"
            f"<b>Last Visit:</b> {last_vis_str}<br>"
            f"<b>Activities:</b> {len(rec.activity_ids)}<br>"
            f"<small style='color: #888;'>Center: {c_lat:.5f}, {c_lng:.5f}</small>"
            f"</div>"
        )

        folium.Polygon(
            locations=poly_coords,
            color="#2b5c8f",
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"Hex: {cell} ({rec.visit_count} visits)",
        ).add_to(hex_group)

    hex_group.add_to(m)

    # Optional Raw GPS Tracks layer
    if activities:
        track_group = folium.FeatureGroup(name=f"Raw Tracks ({len(activities)})", show=False)
        for act_id, points in activities.items():
            if len(points) < 2:
                continue
            track_coords = [[p.lat, p.lng] for p in points]
            folium.PolyLine(
                locations=track_coords,
                color="#e63946",
                weight=2.5,
                opacity=0.7,
                tooltip=f"Activity: {act_id} ({len(points)} pts)",
            ).add_to(track_group)
        track_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(str(out_file))
    return out_file
