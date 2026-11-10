# Hexroute: Strava Territory Competition Route Optimiser

Hexroute is a local Python CLI tool designed to help running teams claim territory in hexagon-based GPS competitions.

## Features

1. **Grid Verification (`hexroute grid check`)**: Verify H3 cell resolution (assumed resolution 8, ~900m) against the competition map.
2. **Activity Ingestion (`hexroute ingest`)**: Ingest bulk Strava GPX/FIT exports into high-performance local activity cache.
3. **Coverage Mapping (`hexroute coverage`)**: Render visited hexes and personal heatmap.
4. **Target Scoring (`hexroute targets`)**: Load, score, and prioritize enemy and unclaimed hexes.
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
pip install -e .
```

To install development dependencies (for running tests):
```bash
pip install -e ".[dev]"
```

### 2. Configure

Copy `.env.example` if using Strava API tokens (optional):
```bash
cp .env.example .env
```

Review or edit `config.toml`:
- `general.h3_resolution`: Default is `8` (~920 m across).
- `general.home_lat` / `general.home_lng`: Your default start coordinates.
- `general.default_budget_km`: Default route budget in kilometres.

---

## Usage

### Phase 1: Verify the Hex Grid

Generate an HTML verification map for your location:

```bash
hexroute grid check --lat 51.5074 --lng -0.1278 --res 8
```

Open `out/grid_check.html` in your browser and compare cell boundaries and centroids with the competition map.

### Inspect Config Status

```bash
hexroute info
```

### Run Tests

```bash
pytest
```
