"""H3 grid utilities and verification map generator."""

from pathlib import Path
from typing import Sequence
import folium
import h3


def latlng_to_cell(lat: float, lng: float, res: int = 8) -> str:
    """Convert latitude and longitude to H3 cell index (v4 API)."""
    return h3.latlng_to_cell(lat, lng, res)


def cell_to_latlng(cell: str) -> tuple[float, float]:
    """Get the center coordinates (lat, lng) of an H3 cell."""
    return h3.cell_to_latlng(cell)


def cell_to_boundary(cell: str) -> list[tuple[float, float]]:
    """Get the boundary polygon vertices as a list of (lat, lng) coordinates."""
    # h3.cell_to_boundary returns tuple of (lat, lng)
    return list(h3.cell_to_boundary(cell))


def get_disk(cell: str, k: int = 1) -> set[str]:
    """Get all H3 cells within k steps of origin cell (including origin)."""
    return set(h3.grid_disk(cell, k))


def generate_grid_check_map(
    lat: float,
    lng: float,
    res: int = 8,
    ring: int = 1,
    out_path: str | Path = "out/grid_check.html",
) -> Path:
    """
    Generate an interactive folium map showing the H3 cell for (lat, lng)
    and its surrounding neighbors up to ring k.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    center_cell = latlng_to_cell(lat, lng, res)
    disk_cells = get_disk(center_cell, ring)

    # Initialize map centered on query point
    m = folium.Map(
        location=[lat, lng],
        zoom_start=14,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # Add query point marker
    folium.Marker(
        location=[lat, lng],
        popup=f"Query Point: {lat:.6f}, {lng:.6f}<br>Cell: {center_cell} (res {res})",
        tooltip="Query Point",
        icon=folium.Icon(color="darkred", icon="crosshairs", prefix="fa"),
    ).add_to(m)

    # Render all cells in the disk
    for cell in disk_cells:
        boundary = cell_to_boundary(cell)
        is_center = cell == center_cell
        cell_lat, cell_lng = cell_to_latlng(cell)

        color = "#e63946" if is_center else "#1d3557"
        fill_color = "#f1faee" if is_center else "#a8dadc"
        fill_opacity = 0.4 if is_center else 0.2
        weight = 3 if is_center else 2

        # Convert boundary (lat, lng) to folium polygon format [[lat, lng], ...]
        poly_coords = [[p[0], p[1]] for p in boundary]

        label = f"<b>H3 Cell:</b> <code>{cell}</code><br><b>Res:</b> {res}<br><b>Center:</b> {cell_lat:.5f}, {cell_lng:.5f}"
        if is_center:
            label = "<b>[TARGET CELL]</b><br>" + label

        folium.Polygon(
            locations=poly_coords,
            color=color,
            weight=weight,
            fill=True,
            fill_color=fill_color,
            fill_opacity=fill_opacity,
            popup=folium.Popup(label, max_width=300),
            tooltip=f"{'Target ' if is_center else ''}Cell: {cell}",
        ).add_to(m)

        # Add center label for easy identification
        folium.CircleMarker(
            location=[cell_lat, cell_lng],
            radius=4,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            tooltip=f"Center of {cell}",
        ).add_to(m)

    m.save(str(out_file))
    return out_file
