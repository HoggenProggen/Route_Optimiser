"""Orienteering route search algorithm on OpenStreetMap walking networks."""

from dataclasses import dataclass
import logging
from typing import Sequence
import networkx as nx

from hexroute.graph import get_nearest_node, get_node_coords, index_graph_cells
from hexroute.grid import cell_to_latlng, latlng_to_cell
from hexroute.targets import HexStatus, ScoredHex

logger = logging.getLogger("hexroute.optimise")


@dataclass
class RoutePlan:
    path_nodes: list[int]
    total_distance_m: float
    claimed_hexes: set[str]
    newly_claimed_hexes: set[str]
    existing_our_hexes: set[str]
    total_score: float
    waypoints: list[int]
    greedy_score: float
    is_loop: bool


class DistanceMatrix:
    """Lazily computes and caches shortest paths between key nodes."""

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        self._dist_cache: dict[tuple[int, int], float] = {}
        self._path_cache: dict[tuple[int, int], list[int]] = {}

    def get_dist_and_path(self, u: int, v: int) -> tuple[float, list[int]]:
        if u == v:
            return 0.0, [u]

        pair = (u, v)
        if pair in self._dist_cache:
            return self._dist_cache[pair], self._path_cache[pair]

        try:
            path = nx.shortest_path(self.graph, source=u, target=v, weight="length")
            dist = float(nx.shortest_path_length(self.graph, source=u, target=v, weight="length"))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            dist = float("inf")
            path = []

        self._dist_cache[pair] = dist
        self._path_cache[pair] = path
        return dist, path

    def get_distance(self, u: int, v: int) -> float:
        return self.get_dist_and_path(u, v)[0]

    def get_path(self, u: int, v: int) -> list[int]:
        return self.get_dist_and_path(u, v)[1]


def compute_tour_distance(waypoints: Sequence[int], matrix: DistanceMatrix, is_loop: bool) -> float:
    """Calculate the total shortest-path distance for a sequence of waypoints."""
    if len(waypoints) < 2:
        return 0.0

    total = 0.0
    for i in range(len(waypoints) - 1):
        d = matrix.get_distance(waypoints[i], waypoints[i + 1])
        if d == float("inf"):
            return float("inf")
        total += d

    if is_loop and waypoints[-1] != waypoints[0]:
        d = matrix.get_distance(waypoints[-1], waypoints[0])
        if d == float("inf"):
            return float("inf")
        total += d

    return total


def two_opt_tour(waypoints: list[int], matrix: DistanceMatrix, is_loop: bool) -> list[int]:
    """Apply 2-opt local search to reduce tour distance without changing visited nodes."""
    if len(waypoints) <= 3:
        return waypoints

    best_tour = list(waypoints)
    best_dist = compute_tour_distance(best_tour, matrix, is_loop)
    improved = True

    while improved:
        improved = False
        n = len(best_tour)
        end_idx = n if is_loop else n - 1
        for i in range(1, end_idx - 1):
            for k in range(i + 1, end_idx):
                new_tour = best_tour[:i] + best_tour[i : k + 1][::-1] + best_tour[k + 1 :]
                new_dist = compute_tour_distance(new_tour, matrix, is_loop)

                if new_dist < best_dist - 0.5:
                    best_tour = new_tour
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break

    return best_tour


def plan_optimal_route(
    graph: nx.MultiDiGraph,
    start_lat: float,
    start_lng: float,
    budget_km: float,
    scored_targets: dict[str, ScoredHex],
    is_loop: bool = True,
    res: int = 8,
) -> RoutePlan:
    """
    Plan a distance-budgeted route that claims the most valuable hexes.
    Picks through-street nodes within target hexagons to avoid cul-de-sac spurs,
    uses Greedy ratio insertion + 2-opt reordering + local search, and eliminates redundant spurs.
    """
    budget_m = budget_km * 1000.0
    start_node = get_nearest_node(graph, start_lat, start_lng)

    matrix = DistanceMatrix(graph)
    node_cells, edge_cells = index_graph_cells(graph, res=res)

    # 1. Map each target cell with positive score to high-quality candidate nodes
    # Prioritise nodes with degree >= 2 (through-streets and intersections) to prevent dead-end spurs
    cell_candidates: dict[str, list[int]] = {}

    for cell, target in scored_targets.items():
        if target.final_score <= 0.0:
            continue

        c_lat, c_lng = target.center_lat, target.center_lng
        c_node = get_nearest_node(graph, c_lat, c_lng)

        # Quick reachability filter from start node
        d_out = matrix.get_distance(start_node, c_node)
        if d_out == float("inf"):
            continue
        d_back = matrix.get_distance(c_node, start_node) if is_loop else 0.0
        if d_out + d_back > budget_m:
            continue

        nodes_in_cell = [n for n, c in node_cells.items() if c == cell]
        if not nodes_in_cell:
            cell_candidates[cell] = [c_node]
            continue

        through_nodes = [n for n in nodes_in_cell if graph.degree(n) >= 2]
        candidates = through_nodes[:6] if through_nodes else [c_node]
        if c_node not in candidates:
            candidates.append(c_node)

        cell_candidates[cell] = candidates

    # 2. Greedy construction with through-node insertion
    tour_nodes = [start_node]
    unvisited_cells = set(cell_candidates.keys())
    claimed_target_cells: set[str] = set()

    start_cell = node_cells.get(start_node)
    if start_cell and start_cell in unvisited_cells:
        unvisited_cells.remove(start_cell)
        claimed_target_cells.add(start_cell)

    while unvisited_cells:
        best_cell: str | None = None
        best_node: int | None = None
        best_pos = -1
        best_ratio = -1.0

        current_dist = compute_tour_distance(tour_nodes, matrix, is_loop)

        for cell in list(unvisited_cells):
            score = scored_targets[cell].final_score
            cands = cell_candidates[cell]

            for pos in range(1, len(tour_nodes) + 1):
                for node in cands:
                    temp_tour = tour_nodes[:pos] + [node] + tour_nodes[pos:]
                    cand_dist = compute_tour_distance(temp_tour, matrix, is_loop)

                    if cand_dist <= budget_m:
                        delta_dist = max(cand_dist - current_dist, 1.0)
                        ratio = score / delta_dist

                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_cell = cell
                            best_node = node
                            best_pos = pos

        if best_cell is not None and best_node is not None:
            tour_nodes.insert(best_pos, best_node)
            unvisited_cells.remove(best_cell)
            claimed_target_cells.add(best_cell)
        else:
            break

    greedy_score = sum(scored_targets[c].final_score for c in claimed_target_cells)

    # 3. 2-opt reordering
    tour_nodes = two_opt_tour(tour_nodes, matrix, is_loop)

    # 4. Secondary insertion search with remaining budget
    for cell in list(unvisited_cells):
        score = scored_targets[cell].final_score
        cands = cell_candidates[cell]
        best_pos = -1
        best_node = -1
        best_dist = float("inf")

        current_dist = compute_tour_distance(tour_nodes, matrix, is_loop)

        for pos in range(1, len(tour_nodes) + 1):
            for node in cands:
                temp_tour = tour_nodes[:pos] + [node] + tour_nodes[pos:]
                cand_dist = compute_tour_distance(temp_tour, matrix, is_loop)

                if cand_dist <= budget_m and cand_dist < best_dist:
                    best_dist = cand_dist
                    best_pos = pos
                    best_node = node

        if best_pos != -1 and best_node != -1:
            tour_nodes.insert(best_pos, best_node)
            unvisited_cells.remove(cell)
            claimed_target_cells.add(cell)
            tour_nodes = two_opt_tour(tour_nodes, matrix, is_loop)

    # 5. Construct complete path on graph
    full_path: list[int] = []
    waypoint_pairs = list(zip(tour_nodes, tour_nodes[1:]))
    if is_loop and len(tour_nodes) > 1 and tour_nodes[-1] != tour_nodes[0]:
        waypoint_pairs.append((tour_nodes[-1], tour_nodes[0]))

    for u, v in waypoint_pairs:
        segment = matrix.get_path(u, v)
        if not full_path:
            full_path.extend(segment)
        else:
            full_path.extend(segment[1:])

    if not full_path:
        full_path = [start_node]

    # 6. Extract all cells crossed by the complete path
    all_crossed_cells: set[str] = set()
    for i in range(len(full_path)):
        node = full_path[i]
        if node in node_cells:
            all_crossed_cells.add(node_cells[node])

        if i < len(full_path) - 1:
            next_node = full_path[i + 1]
            edge_data = graph.get_edge_data(node, next_node)
            if edge_data:
                for k in edge_data.keys():
                    key_tuple = (node, next_node, k)
                    if key_tuple in edge_cells:
                        all_crossed_cells.update(edge_cells[key_tuple])

    total_dist = compute_tour_distance(tour_nodes, matrix, is_loop)
    if total_dist == float("inf"):
        total_dist = 0.0

    # Categorise newly claimed vs existing team territory
    newly_claimed: set[str] = set()
    existing_ours: set[str] = set()

    for c in all_crossed_cells:
        t = scored_targets.get(c)
        if t and t.status == HexStatus.OURS:
            existing_ours.add(c)
        elif t and t.final_score > 0.0:
            newly_claimed.add(c)
        else:
            existing_ours.add(c)

    total_score = sum(scored_targets[c].final_score for c in newly_claimed if c in scored_targets)

    return RoutePlan(
        path_nodes=full_path,
        total_distance_m=total_dist,
        claimed_hexes=all_crossed_cells,
        newly_claimed_hexes=newly_claimed,
        existing_our_hexes=existing_ours,
        total_score=total_score,
        waypoints=tour_nodes,
        greedy_score=greedy_score,
        is_loop=is_loop,
    )
