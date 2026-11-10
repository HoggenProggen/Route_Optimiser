"""Target territory loading, scoring, and visualization."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import folium
from folium.plugins import Fullscreen

from hexroute.grid import cell_to_boundary, cell_to_latlng, get_disk, latlng_to_cell


class HexStatus:
    ENEMY = "enemy"
    UNCLAIMED = "unclaimed"
    OURS = "ours"


@dataclass
class ScoredHex:
    cell: str
    status: str
    base_score: float
    adjacent_to_ours: bool
    final_score: float
    center_lat: float
    center_lng: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "status": self.status,
            "base_score": self.base_score,
            "adjacent_to_ours": self.adjacent_to_ours,
            "final_score": self.final_score,
            "center_lat": self.center_lat,
            "center_lng": self.center_lng,
        }


def load_targets_csv(file_path: str | Path) -> dict[str, str]:
    """
    Load target hexes and their status from a CSV file.
    Format: h3_index,status (e.g. 88195da49bfffff,enemy)
    """
    p = Path(file_path)
    if not p.exists():
        return {}

    targets: dict[str, str] = {}
    with open(p, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#") or row[0].lower() in ("h3_index", "cell", "hex"):
                continue
            cell = row[0].strip()
            status = row[1].strip().lower() if len(row) > 1 else HexStatus.UNCLAIMED
            if status in ("enemy", "unclaimed", "ours"):
                targets[cell] = status
            else:
                targets[cell] = HexStatus.UNCLAIMED

    return targets


def save_targets_csv(targets: dict[str, str], file_path: str | Path) -> Path:
    """Save target hexes to a CSV file."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["h3_index", "status"])
        for cell, status in sorted(targets.items()):
            writer.writerow([cell, status])

    return p


def expand_unclaimed_targets(
    targets: dict[str, str],
    center_lat: float,
    center_lng: float,
    radius_km: float,
    res: int = 8,
) -> dict[str, str]:
    """
    Expand target dictionary with UNCLAIMED hexes within radius_km of center_lat, center_lng.
    Existing 'ours', 'enemy', or 'unclaimed' entries in targets take precedence.
    """
    center_cell = latlng_to_cell(center_lat, center_lng, res)
    # At resolution 8, hexagon center spacing is ~800m
    k = max(2, int((radius_km * 1000.0) / 750.0) + 1)
    disk_cells = get_disk(center_cell, k=k)

    expanded = dict(targets)
    for c in disk_cells:
        if c not in expanded:
            expanded[c] = HexStatus.UNCLAIMED

    return expanded


def score_targets(
    targets: dict[str, str],
    our_territory: set[str] | None = None,
    scoring_config: dict[str, float] | None = None,
) -> dict[str, ScoredHex]:
    """
    Score target hexes based on status and territory adjacency.
    Default scores: enemy=3.0, unclaimed=2.0, ours=0.0, adjacent_bonus=0.5.
    """
    cfg = scoring_config or {
        "enemy": 3.0,
        "unclaimed": 2.0,
        "ours": 0.0,
        "adjacent_bonus": 0.5,
    }

    enemy_weight = float(cfg.get("enemy", 3.0))
    unclaimed_weight = float(cfg.get("unclaimed", 2.0))
    ours_weight = float(cfg.get("ours", 0.0))
    adj_bonus = float(cfg.get("adjacent_bonus", 0.5))

    known_ours = set(our_territory or ())
    # Also add any target explicitly marked as "ours"
    for cell, status in targets.items():
        if status == HexStatus.OURS:
            known_ours.add(cell)

    scored: dict[str, ScoredHex] = {}

    for cell, status in targets.items():
        if status == HexStatus.ENEMY:
            base = enemy_weight
        elif status == HexStatus.UNCLAIMED:
            base = unclaimed_weight
        else:
            base = ours_weight

        # Check adjacency to our territory
        neighbors = get_disk(cell, k=1)
        neighbors.discard(cell)
        is_adjacent = bool(neighbors & known_ours) and status != HexStatus.OURS

        final = base + (adj_bonus if is_adjacent else 0.0)
        c_lat, c_lng = cell_to_latlng(cell)

        scored[cell] = ScoredHex(
            cell=cell,
            status=status,
            base_score=base,
            adjacent_to_ours=is_adjacent,
            final_score=final,
            center_lat=c_lat,
            center_lng=c_lng,
        )

    return scored


def generate_targets_map(
    scored_hexes: dict[str, ScoredHex],
    our_territory: set[str] | None = None,
    out_path: str | Path = "out/targets.html",
    home_lat: float | None = None,
    home_lng: float | None = None,
) -> Path:
    """Generate an interactive Folium map showing scored target hexes."""
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if home_lat is not None and home_lng is not None:
        center_lat, center_lng = home_lat, home_lng
    elif scored_hexes:
        lats = [s.center_lat for s in scored_hexes.values()]
        lngs = [s.center_lng for s in scored_hexes.values()]
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

    enemy_group = folium.FeatureGroup(name="Enemy Hexes (Score: 3+)", show=True)
    unclaimed_group = folium.FeatureGroup(name="Unclaimed Hexes (Score: 2+)", show=True)
    ours_group = folium.FeatureGroup(name="Our Territory (Score: 0)", show=True)

    status_styles = {
        HexStatus.ENEMY: {"color": "#d90429", "fill": "#ef233c", "opacity": 0.5, "group": enemy_group},
        HexStatus.UNCLAIMED: {"color": "#ffb703", "fill": "#fb8500", "opacity": 0.4, "group": unclaimed_group},
        HexStatus.OURS: {"color": "#2a9d8f", "fill": "#2a9d8f", "opacity": 0.3, "group": ours_group},
    }

    # Render scored hexes
    for cell, item in scored_hexes.items():
        boundary = cell_to_boundary(cell)
        poly_coords = [[p[0], p[1]] for p in boundary]
        style = status_styles.get(item.status, status_styles[HexStatus.UNCLAIMED])

        adj_badge = "<span style='color: #2a9d8f; font-weight: bold;'>+0.5 (Border bonus)</span>" if item.adjacent_to_ours else "None"
        popup_html = (
            f"<div style='font-family: sans-serif; font-size: 13px;'>"
            f"<b>H3 Hex:</b> <code>{cell}</code><br>"
            f"<b>Status:</b> <span style='text-transform: uppercase; font-weight: bold;'>{item.status}</span><br>"
            f"<b>Base Score:</b> {item.base_score}<br>"
            f"<b>Adjacency Bonus:</b> {adj_badge}<br>"
            f"<b>Total Value:</b> <span style='color: #d90429; font-size: 15px; font-weight: bold;'>{item.final_score}</span><br>"
            f"<small style='color: #888;'>Center: {item.center_lat:.5f}, {item.center_lng:.5f}</small>"
            f"</div>"
        )

        folium.Polygon(
            locations=poly_coords,
            color=style["color"],
            weight=2.5,
            fill=True,
            fill_color=style["fill"],
            fill_opacity=style["opacity"],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{item.status.upper()}: {cell} (Value: {item.final_score})",
        ).add_to(style["group"])

    # If there are our territory hexes not in targets CSV, render them in ours_group as well
    if our_territory:
        for cell in our_territory:
            if cell not in scored_hexes:
                boundary = cell_to_boundary(cell)
                poly_coords = [[p[0], p[1]] for p in boundary]
                c_lat, c_lng = cell_to_latlng(cell)
                folium.Polygon(
                    locations=poly_coords,
                    color="#2a9d8f",
                    weight=1.5,
                    fill=True,
                    fill_color="#2a9d8f",
                    fill_opacity=0.25,
                    popup=folium.Popup(f"<b>Our Territory:</b> <code>{cell}</code>", max_width=250),
                    tooltip=f"Our Territory: {cell}",
                ).add_to(ours_group)

    enemy_group.add_to(m)
    unclaimed_group.add_to(m)
    ours_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(str(out_file))
    return out_file
