"""OpenStreetMap walking network download, disk caching, and H3 spatial indexing."""

import hashlib
import logging
from pathlib import Path
from typing import Any
import networkx as nx
import osmnx as ox

from hexroute.coverage import haversine_distance
from hexroute.grid import latlng_to_cell

logger = logging.getLogger("hexroute.graph")


def _graph_cache_key(lat: float, lng: float, dist_metres: float, network_type: str) -> str:
    """Generate a deterministic filename for caching graph regions."""
    raw = f"{lat:.4f}_{lng:.4f}_{int(dist_metres)}_{network_type}"
    sig = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    return f"osm_{lat:.4f}_{lng:.4f}_{int(dist_metres)}_{sig}.graphml"


def get_walking_graph(
    lat: float,
    lng: float,
    dist_metres: float = 5000.0,
    cache_dir: str | Path = "cache",
    network_type: str = "walk",
    force_download: bool = False,
) -> nx.MultiDiGraph:
    """
    Download or load from disk cache the OpenStreetMap walking network
    centered at (lat, lng) with radius dist_metres.
    """
    c_dir = Path(cache_dir)
    c_dir.mkdir(parents=True, exist_ok=True)
    cache_file = c_dir / _graph_cache_key(lat, lng, dist_metres, network_type)

    if not force_download and cache_file.exists():
        try:
            logger.info(f"Loading cached OSM graph from {cache_file.name}")
            return ox.load_graphml(cache_file)
        except Exception as e:
            logger.warning(f"Failed to load cached graph: {e}. Re-downloading from OSM.")

    logger.info(f"Downloading OSM {network_type} network for ({lat:.4f}, {lng:.4f}, r={dist_metres:.0f}m)...")
    
    overpass_endpoints = [
        "https://overpass-api.de/api",
        "https://overpass.kumi.systems/api",
        "https://maps.mail.ru/osm/tools/overpass/api",
    ]

    graph = None
    last_err = None
    for endpoint in overpass_endpoints:
        try:
            ox.settings.overpass_endpoint = endpoint
            graph = ox.graph_from_point(
                (lat, lng),
                dist=dist_metres,
                network_type=network_type,
                simplify=True,
            )
            break
        except Exception as e:
            last_err = e
            logger.warning(f"Overpass endpoint {endpoint} failed: {e}. Trying fallback...")

    if graph is None:
        raise RuntimeError(f"Failed to download OSM graph around ({lat}, {lng}): {last_err}") from last_err

    try:
        ox.save_graphml(graph, cache_file)
        logger.info(f"Saved OSM graph to {cache_file}")
    except Exception as e:
        logger.warning(f"Could not cache graph to {cache_file}: {e}")

    return graph


def get_nearest_node(graph: nx.MultiDiGraph, lat: float, lng: float) -> int:
    """Find the nearest graph node to given coordinates."""
    if "crs" not in graph.graph:
        graph.graph["crs"] = "epsg:4326"
    try:
        return int(ox.distance.nearest_nodes(graph, X=lng, Y=lat))
    except Exception:
        best_node = None
        best_dist = float("inf")
        for node, data in graph.nodes(data=True):
            n_lat, n_lng = float(data["y"]), float(data["x"])
            dist = (n_lat - lat) ** 2 + (n_lng - lng) ** 2
            if dist < best_dist:
                best_dist = dist
                best_node = node
        return int(best_node) if best_node is not None else 0


def get_node_coords(graph: nx.MultiDiGraph, node: int) -> tuple[float, float]:
    """Return (lat, lng) for a given graph node."""
    data = graph.nodes[node]
    return float(data["y"]), float(data["x"])


def index_graph_cells(
    graph: nx.MultiDiGraph,
    res: int = 8,
) -> tuple[dict[int, str], dict[tuple[int, int, int], set[str]]]:
    """
    Precompute H3 cell mapping for all nodes and edges in the graph.
    Returns:
      node_cells: mapping from node_id -> H3 cell
      edge_cells: mapping from (u, v, key) -> set of H3 cells crossed by the edge
    """
    node_cells: dict[int, str] = {}
    for node, data in graph.nodes(data=True):
        lat = float(data["y"])
        lng = float(data["x"])
        node_cells[node] = latlng_to_cell(lat, lng, res)

    edge_cells: dict[tuple[int, int, int], set[str]] = {}
    for u, v, k, data in graph.edges(keys=True, data=True):
        u_lat, u_lng = graph.nodes[u]["y"], graph.nodes[u]["x"]
        v_lat, v_lng = graph.nodes[v]["y"], graph.nodes[v]["x"]

        cells = {node_cells[u], node_cells[v]}

        # If edge has detailed geometry coordinates, check all vertices
        if "geometry" in data:
            geom = data["geometry"]
            for lng, lat in geom.coords:
                cells.add(latlng_to_cell(lat, lng, res))
        else:
            # Interpolate edge if length > 50m
            length = float(data.get("length", 0.0))
            if length > 50.0:
                steps = int(length // 40.0)
                for s in range(1, steps):
                    frac = s / (steps + 1)
                    i_lat = u_lat + frac * (v_lat - u_lat)
                    i_lng = u_lng + frac * (v_lng - u_lng)
                    cells.add(latlng_to_cell(i_lat, i_lng, res))

        edge_cells[(u, v, k)] = cells

    return node_cells, edge_cells
