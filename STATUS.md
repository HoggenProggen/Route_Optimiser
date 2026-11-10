# Project Status & Handover Guide: Hexroute

This document tracks the overall development state, architectural decisions, completed milestones, and immediate next steps for the Hexroute Optimiser. It is designed to allow any AI agent or engineer to seamlessly pick up where we left off.

---

## 1. Executive Summary

**Project:** Hexroute (Strava Territory Competition Route Optimiser)  
**Objective:** A local Python CLI tool that parses past GPS activity data (GPX/FIT bulk export), maps covered H3 hexagons, scores target territory, and uses OpenStreetMap walking networks to calculate distance-budgeted optimal running routes that maximize territory claim score.  
**Environment:** macOS / Linux, Python 3.11+, standalone local CLI (no server, no external database).

---

## 2. Overall Phase Progress

| Phase | Description | Status | Notes / Outcomes |
|---|---|---|---|
| **Phase 0** | Repo Scaffolding & Setup | **COMPLETED** (✓) | Layout created, `pyproject.toml`, `.gitignore`, `.env.example`, `config.toml`, `.venv` installed. |
| **Phase 1** | Hex Grid Assumption Check | **COMPLETED** (✓) | H3 resolution 8 verified against competition site. `hexroute grid check` works and generates Folium maps. |
| **Phase 1 🛑** | Human Verification Checkpoint | **CONFIRMED** (✓) | **Human confirmed hex cells at resolution 8 align accurately with the competition map.** |
| **Phase 2** | Ingest Activity History | **COMPLETED** (✓) | `hexroute ingest` parses GPX and FIT files in `data/`, extracts GPS point streams, caches to disk (`cache/activities_*.json.gz`). |
| **Phase 3** | Coverage Map | **COMPLETED** (✓) | `hexroute coverage` maps points -> H3 cells with track densification (40m steps), generates `out/coverage.html` with raw track toggle. |
| **Phase 4** | Targets & Scoring | **COMPLETED** (✓) | `hexroute targets init` & `hexroute targets show` handle territory state CSV (`unclaimed`, `enemy`, `ours`), scoring with adjacency bonuses, and Folium map rendering. |
| **Phase 5** | Competition API Integration | **COMPLETED** (✓) | Connected to `https://api.strods.uk/clubs/2345/land-grab`. Native Land-Grab parser calculates ownership, leader ties, flips, and syncs 1,065 competition hexes into `data/targets.csv`. |
| **Phase 6** | Route Optimiser (Core Engine) | **COMPLETED** (✓) | `hexroute plan` downloads OSM walking graphs via `osmnx`, auto-expands reachable unvisited territory with unclaimed hexes, runs orienteering solver, exports `out/route.gpx` and `out/route.html`. |
| **Phase 7** | Polish & Export | **COMPLETED** (✓) | GPX export, high-fidelity geometry interpolation, test suite with 28 passing unit tests. |

---

## 3. Verified Assumptions & Key Decisions

1. **H3 Grid Resolution:**
   - **Resolution:** `8` (hexagons are ~920 m across).
   - **Verification:** Verified by generating `out/grid_check.html` and visually matching with the competition leaderboard map.
   - **Configuration:** Set in [`config.toml`](config.toml) under `[general].h3_resolution = 8`.

2. **Data Privacy & Storage:**
   - All personal GPS files reside in `data/` (gitignored).
   - Generated maps and GPX routes are saved to `out/` (gitignored).
   - Cached graphs and parsed activity streams are stored in `cache/` (gitignored).
   - No hardcoded secrets; tokens go in `.env` (gitignored).

3. **Software Stack Versions:**
   - `h3` (v4 API: `latlng_to_cell`, `cell_to_latlng`, `cell_to_boundary`, `grid_disk`)
   - `osmnx` (v2.x) & `networkx` (v3.x) for pathfinding
   - `gpxpy` & `fitparse` for GPX/FIT parsing
   - `shapely` for geometry & track densification
   - `folium` for interactive HTML map visualizations
   - `typer` for CLI commands
   - `tomllib` (Python standard library) for TOML configuration parsing
   - `pytest` for unit testing

---

## 4. Current Codebase Map

```
Route_Optimiser/
├── .env.example              # Template for optional Strava API / competition tokens
├── .gitignore                # Ignores .venv, .env, data/, out/, cache/, tests cache
├── config.toml               # User configuration (coordinates, budget, scoring weights, paths)
├── pyproject.toml            # Python packaging and dependency specifications
├── README.md                 # Project introduction and user guide
├── TASK.md                   # Original task specification and phased brief
├── STATUS.md                 # This file (handover and state tracking)
├── src/hexroute/
│   ├── __init__.py           # Package version definition
│   ├── config.py             # Config loader with fallback defaults
│   ├── grid.py               # H3 v4 utilities and grid check map generator
│   ├── ingest.py             # GPX/FIT ingestion with gzip/JSON caching
│   ├── coverage.py           # Track densification, visit counts, coverage map generator
│   ├── targets.py            # CSV loading, target scoring with adjacency bonuses
│   ├── graph.py              # OSM walking network download, disk cache, node/edge H3 indexing
│   ├── optimise.py           # Orienteering problem solver (Greedy + 2-opt + local search)
│   ├── export.py             # GPX file builder and Folium route map generator
│   └── cli.py                # Typer CLI application (info, grid check, ingest, coverage, targets, plan)
├── tests/
│   ├── __init__.py
│   ├── test_grid.py          # Unit tests for grid operations and CLI
│   ├── test_ingest.py        # Unit tests for GPX/FIT ingestion and caching
│   ├── test_coverage.py      # Unit tests for track densification and coverage
│   ├── test_targets.py       # Unit tests for target scoring and CSV loading
│   └── test_optimise.py      # Unit tests for route planning and GPX export (24 tests total)
├── data/                     # (Gitignored) Place Strava bulk export GPX/FIT files here
├── out/                      # (Gitignored) Output maps and GPX files
└── cache/                    # (Gitignored) Parsed activity caches and OSM graphs
```

---

## 5. How to Run & Validate the Project

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run full test suite (24 tests)
pytest

# 3. Check CLI info
hexroute info

# 4. Verify grid check map
hexroute grid check --lat 51.5074 --lng -0.1278 --res 8

# 5. Ingest activities (when files are in data/)
hexroute ingest

# 6. Generate coverage map
hexroute coverage

# 7. Initialize & view targets
hexroute targets init --ring 2
hexroute targets show

# 8. Plan an optimal 10km loop route
hexroute plan --km 10 --loop
```
