"""Tests for route optimisation, graph indexing, and GPX/map export."""

from pathlib import Path
import networkx as nx
import pytest

from hexroute.export import export_route_gpx, generate_route_map, get_path_coordinates
from hexroute.graph import index_graph_cells
from hexroute.grid import latlng_to_cell
from hexroute.optimise import DistanceMatrix, plan_optimal_route, two_opt_tour
from hexroute.targets import HexStatus, ScoredHex


@pytest.fixture
def synthetic_graph() -> nx.MultiDiGraph:
    """
    Construct a synthetic walking grid graph around London (51.5074, -0.1278).
    Creates a 3x3 grid of nodes with 500m edges.
    """
    G = nx.MultiDiGraph()
    # 3x3 grid with spacing ~ 0.005 deg (~500m)
    base_lat = 51.5074
    base_lng = -0.1278
    step = 0.005

    for r in range(3):
        for c in range(3):
            node_id = r * 3 + c
            lat = base_lat + r * step
            lng = base_lng + c * step
            G.add_node(node_id, y=lat, x=lng)

    # Add bidirectional edges
    for r in range(3):
        for c in range(3):
            u = r * 3 + c
            # East neighbor
            if c < 2:
                v = r * 3 + (c + 1)
                G.add_edge(u, v, key=0, length=500.0)
                G.add_edge(v, u, key=0, length=500.0)
            # North neighbor
            if r < 2:
                v = (r + 1) * 3 + c
                G.add_edge(u, v, key=0, length=500.0)
                G.add_edge(v, u, key=0, length=500.0)

    return G


def test_distance_matrix_and_two_opt(synthetic_graph: nx.MultiDiGraph) -> None:
    matrix = DistanceMatrix(synthetic_graph)
    # Distance between node 0 and node 2 is 1000m (0 -> 1 -> 2)
    dist, path = matrix.get_dist_and_path(0, 2)
    assert dist == 1000.0
    assert path == [0, 1, 2]

    # Test 2-opt reordering
    tour = [0, 8, 2, 6]
    optimized = two_opt_tour(tour, matrix, is_loop=True)
    assert len(optimized) == len(tour)


def test_index_graph_cells(synthetic_graph: nx.MultiDiGraph) -> None:
    node_cells, edge_cells = index_graph_cells(synthetic_graph, res=8)
    assert len(node_cells) == 9
    assert len(edge_cells) > 0
    for cell in node_cells.values():
        assert isinstance(cell, str)


def test_plan_optimal_route(synthetic_graph: nx.MultiDiGraph) -> None:
    # Setup scored targets for some nodes in synthetic graph
    res = 8
    scored_targets: dict[str, ScoredHex] = {}

    for node_id in [1, 2, 4, 5, 8]:
        data = synthetic_graph.nodes[node_id]
        lat, lng = data["y"], data["x"]
        cell = latlng_to_cell(lat, lng, res)
        scored_targets[cell] = ScoredHex(
            cell=cell,
            status=HexStatus.ENEMY,
            base_score=3.0,
            adjacent_to_ours=True,
            final_score=3.5,
            center_lat=lat,
            center_lng=lng,
        )

    # Budget of 3.0 km loop starting at node 0 (51.5074, -0.1278)
    plan = plan_optimal_route(
        graph=synthetic_graph,
        start_lat=51.5074,
        start_lng=-0.1278,
        budget_km=3.0,
        scored_targets=scored_targets,
        is_loop=True,
        res=res,
    )

    assert plan.total_distance_m <= 3000.0
    assert len(plan.path_nodes) >= 2
    assert plan.total_score >= plan.greedy_score
    assert len(plan.claimed_hexes) >= 1
    # Check that path is continuous on graph
    for u, v in zip(plan.path_nodes, plan.path_nodes[1:]):
        assert synthetic_graph.has_edge(u, v)


def test_export_gpx_and_map(synthetic_graph: nx.MultiDiGraph, tmp_path: Path) -> None:
    path_nodes = [0, 1, 2, 5, 4, 0]
    gpx_file = tmp_path / "route.gpx"
    map_file = tmp_path / "route.html"

    res_gpx = export_route_gpx(synthetic_graph, path_nodes, out_path=gpx_file)
    assert res_gpx.exists()
    content = res_gpx.read_text(encoding="utf-8")
    assert "<gpx" in content
    assert "<trkpt" in content

    res_map = generate_route_map(
        graph=synthetic_graph,
        path_nodes=path_nodes,
        claimed_hexes={"88195da49bfffff"},
        scored_targets={},
        total_distance_m=2500.0,
        total_score=10.5,
        out_path=map_file,
    )
    assert res_map.exists()
    map_content = res_map.read_text(encoding="utf-8")
    assert "Hexroute Optimiser" in map_content
