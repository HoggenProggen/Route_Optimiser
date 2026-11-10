"""Competition site data fetcher and territory state parser."""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import time
from typing import Any
import urllib.parse
import urllib.request

from hexroute.config import load_config
from hexroute.grid import latlng_to_cell
from hexroute.targets import HexStatus, save_targets_csv

logger = logging.getLogger("hexroute.fetcher")


@dataclass
class HexOwnership:
    cell: str
    owner_team: str | None
    enemy_visits: int = 0
    our_visits: int = 0
    status: str = HexStatus.UNCLAIMED
    visits_to_flip: int = 1
    tie_held_by_us: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "owner_team": self.owner_team,
            "enemy_visits": self.enemy_visits,
            "our_visits": self.our_visits,
            "status": self.status,
            "visits_to_flip": self.visits_to_flip,
            "tie_held_by_us": self.tie_held_by_us,
        }


def fetch_competition_data(
    endpoint_url: str,
    session_cookie: str | None = None,
    headers: dict[str, str] | None = None,
    cache_path: str | Path = "cache/competition_raw.json",
    cache_ttl_seconds: int = 300,  # 5 minutes cache TTL
    force_refresh: bool = False,
) -> dict[str, Any] | list[Any]:
    """
    Fetch raw territory/overview data from competition endpoint with rate-limiting and caching.
    Gracefully falls back to existing cache if network or auth error occurs.
    """
    c_path = Path(cache_path)
    c_path.parent.mkdir(parents=True, exist_ok=True)

    if not force_refresh and c_path.exists():
        mtime = c_path.stat().st_mtime
        if time.time() - mtime < cache_ttl_seconds:
            logger.info("Using cached competition data (TTL valid)")
            try:
                with open(c_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading cache: {e}. Fetching live data.")

    cookie = session_cookie or os.environ.get("COMPETITION_SESSION_COOKIE") or os.environ.get("STRODS_COOKIE") or os.environ.get("STRODS_TOKEN")
    if cookie and not cookie.startswith("stToken=") and not ";" in cookie and "." in cookie:
        cookie = f"stToken={cookie}"

    req_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://strods.uk",
        "Referer": "https://strods.uk/",
    }
    if headers:
        req_headers.update(headers)
    if cookie:
        req_headers["Cookie"] = cookie

    req = urllib.request.Request(endpoint_url, headers=req_headers)

    logger.info(f"Fetching competition data from {endpoint_url}...")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = response.read().decode("utf-8")
            parsed = json.loads(raw_data)

        with open(c_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        return parsed
    except urllib.error.HTTPError as e:
        # If API returned 500/401/403 and we have a cached copy, fall back with warning
        fallback_candidates = [c_path, Path("data/land_grab.json")]
        for fb in fallback_candidates:
            if fb.exists():
                logger.warning(f"Endpoint returned HTTP {e.code}: {e.reason}. Using local fallback '{fb}'.")
                with open(fb, "r", encoding="utf-8") as f:
                    return json.load(f)

        raise RuntimeError(
            f"HTTP Error {e.code}: {e.reason} while requesting '{endpoint_url}'.\n"
            f"Note: api.strods.uk requires an authenticated session cookie. "
            f"Pass --cookie 'stToken=...' or use --file data/land_grab.json."
        ) from e
    except urllib.error.URLError as e:
        fallback_candidates = [c_path, Path("data/land_grab.json")]
        for fb in fallback_candidates:
            if fb.exists():
                logger.warning(f"Network error ({e.reason}). Using local fallback '{fb}'.")
                with open(fb, "r", encoding="utf-8") as f:
                    return json.load(f)

        raise RuntimeError(f"Network error connecting to '{endpoint_url}': {e.reason}") from e


def parse_competition_payload(
    payload: Any,
    our_team_name: str,
    res: int = 8,
) -> dict[str, HexOwnership]:
    """
    Parse varied JSON / GeoJSON / Land-Grab structures from MapLibre GL competition backends
    into standardized HexOwnership mappings.
    """
    results: dict[str, HexOwnership] = {}
    our_team_clean = our_team_name.strip().lower()

    # Case 0: Strods Land Grab API structure
    # Contains: 'cells' (list of H3 strings), 'teams' (list of team dicts), 'activities' (list of activity logs)
    if isinstance(payload, dict) and "cells" in payload and "teams" in payload and "activities" in payload:
        cells_list: list[str] = [str(c) for c in payload.get("cells", [])]
        teams_list: list[dict[str, Any]] = payload.get("teams", [])

        # Find our team index and map team indices to names
        team_names: dict[int, str] = {}
        our_team_idx: int | None = None

        if "your_team" in payload and isinstance(payload["your_team"], int):
            configured_team_idx = payload["your_team"]
            if 0 <= configured_team_idx < len(teams_list):
                our_team_idx = configured_team_idx

        for idx, t_obj in enumerate(teams_list):
            t_name = str(t_obj.get("name", f"Team {idx}"))
            team_names[idx] = t_name
            if t_name.strip().lower() == our_team_clean:
                our_team_idx = idx

        if our_team_idx is None and teams_list:
            our_team_idx = 0  # Fallback to first team if not found

        # Initialize tracking for all cells in the competition universe
        # Each cell tracks: visits_by_team: dict[int, int], current_owner_idx: int | None, leader_visits: int
        cell_visits: dict[int, dict[int, int]] = {i: {} for i in range(len(cells_list))}
        cell_owners: dict[int, int | None] = {i: None for i in range(len(cells_list))}
        cell_leader_visits: dict[int, int] = {i: 0 for i in range(len(cells_list))}

        # Track unique athlete visits per day per cell (Limit: 1 count per athlete per day per cell)
        # Key: (athlete_str, day_int, cell_idx)
        seen_athlete_day_cells: set[tuple[str, int, int]] = set()

        activities = payload.get("activities", [])
        # Sort activities chronologically by 'minutes' if present
        sorted_activities = sorted(
            activities,
            key=lambda a: a.get("minutes", 0) if isinstance(a, dict) else 0,
        )

        for act in sorted_activities:
            if not isinstance(act, dict):
                continue

            act_team = act.get("team")
            if act_team is None or not isinstance(act_team, int):
                continue

            athlete = str(act.get("athlete", "anonymous"))
            minutes = int(act.get("minutes", 0))
            day = minutes // 1440  # 1440 minutes per day

            act_cell_indices = act.get("cells", [])
            for c_idx in act_cell_indices:
                if not isinstance(c_idx, int) or c_idx < 0 or c_idx >= len(cells_list):
                    continue

                athlete_key = (athlete, day, c_idx)
                if athlete_key in seen_athlete_day_cells:
                    # Already counted for this athlete on this day
                    continue
                seen_athlete_day_cells.add(athlete_key)

                # Increment team visits for this cell
                curr_visits = cell_visits[c_idx].get(act_team, 0) + 1
                cell_visits[c_idx][act_team] = curr_visits

                # Check leadership and ownership flip
                leader_vis = cell_leader_visits[c_idx]
                curr_owner = cell_owners[c_idx]

                if curr_visits > leader_vis:
                    # Team exceeded leader count -> captures the hex
                    cell_owners[c_idx] = act_team
                    cell_leader_visits[c_idx] = curr_visits
                # Note: On exact tie (curr_visits == leader_vis), ownership does not flip (retained by whoever reached it first)

        # Convert calculated cell state into HexOwnership
        for c_idx, cell_h3 in enumerate(cells_list):
            owner_idx = cell_owners[c_idx]
            team_counts = cell_visits[c_idx]

            our_v = team_counts.get(our_team_idx, 0) if our_team_idx is not None else 0
            
            # Enemy visits is highest visit count among enemy teams
            enemy_counts = [v for t_i, v in team_counts.items() if t_i != our_team_idx]
            max_enemy_v = max(enemy_counts) if enemy_counts else 0

            if owner_idx is None:
                # Unclaimed
                status = HexStatus.UNCLAIMED
                owner_name = None
                visits_to_flip = 1
            elif owner_idx == our_team_idx:
                # Ours
                status = HexStatus.OURS
                owner_name = team_names.get(owner_idx, our_team_name)
                visits_to_flip = 0
            else:
                # Enemy
                status = HexStatus.ENEMY
                owner_name = team_names.get(owner_idx, f"Enemy Team {owner_idx}")
                # To take it, we must strictly exceed current owner's visits
                owner_visits = team_counts.get(owner_idx, 0)
                visits_to_flip = max(1, (owner_visits + 1) - our_v)

            results[cell_h3] = HexOwnership(
                cell=cell_h3,
                owner_team=owner_name,
                enemy_visits=max_enemy_v,
                our_visits=our_v,
                status=status,
                visits_to_flip=visits_to_flip,
                tie_held_by_us=(owner_idx == our_team_idx),
            )

        return results

    # Case 1: GeoJSON FeatureCollection
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        features = payload.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})

            cell = props.get("h3") or props.get("h3_index") or props.get("cell") or props.get("id")
            if not cell and geom.get("type") == "Polygon":
                coords = geom.get("coordinates", [[]])[0]
                if coords:
                    avg_lng = sum(p[0] for p in coords) / len(coords)
                    avg_lat = sum(p[1] for p in coords) / len(coords)
                    cell = latlng_to_cell(avg_lat, avg_lng, res)

            if not cell:
                continue

            owner = props.get("team") or props.get("owner") or props.get("team_name")
            visits = int(props.get("visits") or props.get("count") or 1)

            owner_clean = str(owner).strip().lower() if owner else None
            is_ours = owner_clean == our_team_clean if owner_clean else False

            status = HexStatus.OURS if is_ours else (HexStatus.ENEMY if owner else HexStatus.UNCLAIMED)
            results[str(cell)] = HexOwnership(
                cell=str(cell),
                owner_team=str(owner) if owner else None,
                enemy_visits=visits if not is_ours and owner else 0,
                our_visits=visits if is_ours else 0,
                status=status,
                visits_to_flip=1 if not owner else (visits + 1 if not is_ours else 0),
            )

    # Case 2: List of hex objects or dict mapping
    elif isinstance(payload, (list, dict)):
        items = payload if isinstance(payload, list) else (
            payload.get("hexes") or payload.get("territory") or payload.get("data") or list(payload.values())
        )

        if isinstance(items, dict):
            items = [{"h3": k, **(v if isinstance(v, dict) else {"owner": v})} for k, v in items.items()]

        for item in items:
            if not isinstance(item, dict):
                continue

            cell = item.get("h3") or item.get("h3_index") or item.get("cell") or item.get("hex") or item.get("id")
            if not cell and "lat" in item and "lng" in item:
                cell = latlng_to_cell(float(item["lat"]), float(item["lng"]), res)

            if not cell:
                continue

            owner = item.get("team") or item.get("owner") or item.get("team_name") or item.get("held_by")
            owner_clean = str(owner).strip().lower() if owner else None
            is_ours = owner_clean == our_team_clean if owner_clean else False

            status = HexStatus.OURS if is_ours else (HexStatus.ENEMY if owner else HexStatus.UNCLAIMED)
            results[str(cell)] = HexOwnership(
                cell=str(cell),
                owner_team=str(owner) if owner else None,
                status=status,
            )

    return results


def sync_competition_targets(
    endpoint_url: str | None = None,
    file_path: str | Path | None = None,
    our_team_name: str = "Agile & Fragile",
    session_cookie: str | None = None,
    out_csv_path: str | Path = "data/targets.csv",
    cache_path: str | Path = "cache/competition_raw.json",
    res: int = 8,
    force_refresh: bool = False,
) -> tuple[dict[str, HexOwnership], Path]:
    """
    Fetch or load competition state, parse hex ownership, and update data/targets.csv.
    """
    if file_path and Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as f:
            raw_payload = json.load(f)
    elif endpoint_url:
        raw_payload = fetch_competition_data(
            endpoint_url=endpoint_url,
            session_cookie=session_cookie,
            cache_path=cache_path,
            force_refresh=force_refresh,
        )
    elif Path(cache_path).exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            raw_payload = json.load(f)
    else:
        raise ValueError("Must provide either endpoint_url or an existing file_path / cache_path.")

    ownership = parse_competition_payload(raw_payload, our_team_name=our_team_name, res=res)
    target_dict = {cell: o.status for cell, o in ownership.items()}

    saved_path = save_targets_csv(target_dict, out_csv_path)
    return ownership, saved_path
