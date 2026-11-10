# Hexroute: Strava Territory Competition Route Optimiser

Hexroute is an automated route planning and orienteering engine designed for teams competing in hexagon-based territory games (such as the Strods Land-Grab competition). Operating at **Uber H3 resolution 8** (~920 m across), it optimizes running and cycling routes over real **OpenStreetMap (OSM)** networks to maximize territory capture points within a chosen distance budget.

---

## Key Features

- 🌐 **Interactive Point-and-Click Web UI (`hexroute serve`)**: Click anywhere on an interactive Leaflet map to set your starting location, choose your distance and exercise mode (Walk/Run or Cycling), plan your route, and instantly download a `.gpx` file for Garmin, Strava, Wahoo, or Apple Watch.
- 🎯 **Target Scoring Engine**: Automatically values enemy territory flips (+3.0 pts), unclaimed frontier hexes (+2.0 pts), and adds territory adjacency bonuses (+0.5 pts) while recognizing existing team territory.
- 🚴 **Multi-Modal Routing**: Supports pedestrian walking networks (footpaths, trails, pedestrian paths) and cycling networks (cycleways, bridleways, roads).
- 🔄 **Live Competition Sync (`hexroute fetch`)**: Pulls real-time territory ownership directly from the Strods competition endpoint.
- 📍 **Historical GPX/FIT Ingestion & Coverage Mapping (`hexroute ingest` & `hexroute coverage`)**: Ingests bulk activity files with 40-metre track densification to map historical team coverage without missing corners.
- 🧩 **Anti-Spur Orienteering Solver**: Solves a TSP orienteering problem using high-degree through-nodes to prevent dead-end turnaround spurs.

---

## Clean Setup Guide (Fresh Installation)

### Prerequisites

- **macOS** or **Linux**
- **Python 3.11+** (Python 3.12 recommended)
- **Git**

---

### Step 1: Clone Repository

```bash
git clone https://github.com/hexroute/Route_Optimiser.git
cd Route_Optimiser
```

---

### Step 2: Create & Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

> **Tip:** Whenever you open a new terminal window in this project directory, activate the environment with `source .venv/bin/activate`.

---

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

Verify the installation:

```bash
hexroute --help
```

---

### Step 4: Configuration

Review or customize `config.toml` to set your team name, club ID, and default home coordinates:

```toml
[general]
h3_resolution = 8          # Competition H3 hex resolution (~920m across)
home_lat = 51.5074         # Default starting latitude (e.g. 51.5074)
home_lng = -0.1278         # Default starting longitude (e.g. -0.1278)
default_budget_km = 8.0    # Default route distance budget in km

[competition]
club_id = "2345"                   # Strods Club ID
team_name = "Agile & Fragile"      # Your team name
team_colour = "#8aa4c2"            # Team hex color

[scoring]
enemy_capture_score = 3.0    # Points for taking an enemy cell
unclaimed_score = 2.0        # Points for capturing an unclaimed cell
our_cell_score = 0.0         # Points for passing through existing team cell
adjacent_bonus = 0.5         # Bonus for expanding adjacent friendly territory

[paths]
data_dir = "data"
out_dir = "out"
cache_dir = "cache"
```

---

## Quick Start: Interactive Web App

The easiest way to plan routes for you and your team is using the built-in Web UI:

```bash
hexroute serve
# or alias:
hexroute ui
```

Your browser will automatically open to **`http://127.0.0.1:8080`**.

### How to use the Web UI:

1. **Set Starting Location**: Click anywhere on the map to place or drag the starting pin, or click **"📍 GPS"** to use your current location.
2. **Select Exercise Mode**: Choose **🏃 Run / Walk** or **🚴 Cycling**.
3. **Choose Distance Budget**: Drag the slider (1 km – 30 km) or click a quick preset (`[3k]`, `[5k]`, `[8k]`, `[10k]`, `[15k]`, `[20k]`).
4. **Select Route Type**: Choose **Circular Loop** (returns to start) or **One-Way**.
5. **Click "Plan Optimal Route"**: The optimizer downloads local OSM networks, solves the orienteering TSP, renders newly captured hexes and score gains, and prepares your GPX file.
6. **Download GPX**: Click **"📥 Download GPX"** to load the file onto your GPS watch or cycling computer.

---

## CLI Command Reference

All functions can also be run directly from the command line:

### 1. Plan a Route (`hexroute plan`)

```bash
# 8 km running loop from default home coordinates
hexroute plan -k 8.0

# 15 km cycling loop from specific coordinates
hexroute plan -k 15.0 -m bike --lat 51.5074 --lng -0.1278

# 6 km one-way route
hexroute plan -k 6.0 --one-way
```

**Outputs generated:**

- `out/route.gpx`: Standard turn-by-turn GPX track.
- `out/route.html`: Standalone interactive HTML Leaflet map.

---

### 2. Fetch Live Competition Territory (`hexroute fetch`)

Pulls the latest ownership state from the Strods Land-Grab competition API:

```bash
hexroute fetch
```

Updates `data/targets.csv` with current team ownership.

---

### 3. Ingest GPS History (`hexroute ingest`)

Place any bulk Strava export `.gpx`, `.fit`, `.gpx.gz`, or `.fit.gz` files into `data/`, then ingest them:

```bash
hexroute ingest
```

Parsed activity point streams are cached in `cache/` for instant subsequent analysis.

---

### 4. Generate Personal Coverage Heatmap (`hexroute coverage`)

Maps every H3 hex you have historically visited:

```bash
hexroute coverage
```

Generates `out/coverage.html` with activity heatmaps and visited hex statistics.

---

### 5. View Scored Targets Map (`hexroute targets show`)

Visualizes current target scoring, territory frontiers, and adjacent bonus opportunities:

```bash
hexroute targets show
```

Generates `out/targets.html`.

---

### 6. Verify Hex Grid Alignment (`hexroute grid check`)

Visualizes H3 hexagons around any location to confirm resolution and alignment with competition boundaries:

```bash
hexroute grid check --lat 51.5074 --lng -0.1278 --ring 2
```

Generates `out/grid_check.html`.

---

### 7. View Current System Info (`hexroute info`)

```bash
hexroute info
```

---

## Running the Unit Test Suite

Run the full automated test suite (32 unit tests):

```bash
pytest -v
```

Expected output:

```text
============================== 32 passed in 1.80s ==============================
```

---

## Project Structure

```text
Route_Optimiser/
├── config.toml              # Project configuration (coords, budget, team, scoring)
├── pyproject.toml           # Package build spec and dependency requirements
├── README.md                # Documentation & clean setup guide
├── src/
│   └── hexroute/
│       ├── __init__.py
│       ├── cli.py           # Typer CLI application (commands: plan, serve, ingest, etc.)
│       ├── config.py        # TOML configuration loader and validator
│       ├── coverage.py      # GPS track densification (40m) and coverage map generator
│       ├── export.py        # GPX exporter and Folium interactive map generator
│       ├── fetcher.py       # Live Strods land-grab competition data fetcher
│       ├── graph.py         # OSMnx network downloader, caching & H3 graph indexing
│       ├── grid.py          # H3 v4 grid conversions, boundaries, and disk search
│       ├── ingest.py        # Bulk GPX & FIT parser and disk caching engine
│       ├── optimise.py      # Orienteering TSP solver with 2-opt and high-degree node entry
│       ├── server.py        # Web UI single-page application & local REST API server
│       └── targets.py       # Hex scoring engine, frontier expansion & CSV management
├── tests/                   # Pytest test suite (32 unit tests)
│   ├── test_coverage.py
│   ├── test_fetcher.py
│   ├── test_grid.py
│   ├── test_ingest.py
│   ├── test_optimise.py
│   ├── test_server.py
│   └── test_targets.py
├── data/                    # User data directory (targets.csv, GPX/FIT uploads)
├── out/                     # Generated route.gpx, route.html, maps
└── cache/                   # OSM network cache (.graphml) and parsed activity streams
```

---

## Scoring Mechanics & Algorithm Overview

1. **Spatial Indexing**: Converts coordinates to H3 resolution 8 cells (~920 m diagonal diameter).
2. **Scoring Function**:
   - $\text{Score}(\text{Enemy}) = 3.0\text{ pts}$
   - $\text{Score}(\text{Unclaimed}) = 2.0\text{ pts}$
   - $\text{Score}(\text{Friendly Adjacent Bonus}) = +0.5\text{ pts}$
   - $\text{Score}(\text{Already Held}) = 0.0\text{ pts}$
3. **Graph Traversal & Anti-Spur Logic**:
   - Filters candidate target nodes by connectivity degree ($k \ge 3$) to select clean through-nodes rather than cul-de-sacs.
   - Computes Dijkstra shortest-path distance matrices on real OSM walking/cycling graphs.
   - Runs a greedy knapsack heuristic with 2-opt tour improvement to maximize territory points within the distance budget.
