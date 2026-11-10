# Hexroute: Strava Territory Competition Route Optimiser

Hexroute is a local Python CLI tool designed to help running teams claim territory in hexagon-based GPS competitions.

## Features

1. **Grid Verification (`hexroute grid check`)**: Verify H3 cell resolution (assumed resolution 8, ~920m) against the competition map.
2. **Activity Ingestion (`hexroute ingest`)**: Ingest bulk Strava GPX/FIT exports into high-performance local activity cache.
3. **Coverage Mapping (`hexroute coverage`)**: Render visited hexes and personal heatmap with track densification.
4. **Target Scoring (`hexroute targets`)**: Load, score, and prioritize enemy and unclaimed hexes with adjacency bonuses.
5. **Route Optimisation (`hexroute plan`)**: Solve the orienteering problem on real OpenStreetMap walking networks within a distance budget and export GPX files.

---

## Installation & Setup

### Prerequisites
- macOS / Linux
- Python 3.11+
- Recommended: Virtual environment (`venv`)

### 1. Clone & create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Configure

Copy `.env.example` if using Strava API tokens or competition cookies (optional):
```bash
cp .env.example .env
```

Review or edit `config.toml`:
- `general.h3_resolution`: Default is `8` (~920 m across).
- `general.home_lat` / `general.home_lng`: Your default start coordinates.
- `general.default_budget_km`: Default route budget in kilometres.
- `scoring`: Weights for `enemy`, `unclaimed`, `ours`, and `adjacent_bonus`.

---

## Workflow & Commands

### 1. Verify Grid Alignment
Generate an HTML verification map for your location to compare against the competition site:
```bash
hexroute grid check --lat 51.5074 --lng -0.1278 --res 8
```
Open `out/grid_check.html` in your browser.

### 2. Ingest Strava History
Place your Strava bulk export (`.gpx`, `.fit`, `.gpx.gz`, `.fit.gz`) into `data/`, then run:
```bash
hexroute ingest
```

### 3. Generate Personal Coverage Map
Calculate all visited H3 cells and render the territory coverage heatmap:
```bash
hexroute coverage
```
Open `out/coverage.html` in your browser.

### 4. Manage & Score Target Territory
Initialize or inspect target cells:
```bash
# Initialize targets around your location (ring radius 2 = 19 hexes)
hexroute targets init --ring 2

# View scored targets map (includes enemy, unclaimed, and adjacency bonuses)
hexroute targets show
```
Open `out/targets.html` in your browser.

### 5. Plan an Optimal Route
Calculate an optimal distance-budgeted route on real OpenStreetMap walking networks:
```bash
# 10 km loop route starting from home coordinates
hexroute plan --km 10 --loop

# 7 km one-way route starting from specific coordinates
hexroute plan --km 7 --one-way --lat 51.5074 --lng -0.1278
```
Outputs:
- `out/route.gpx`: Ready to upload to Strava, Garmin, or Apple Watch.
- `out/route.html`: Interactive route visualization with claimed hexes and score summary.

### 6. Inspect Configuration & Run Tests
```bash
hexroute info
pytest
```
