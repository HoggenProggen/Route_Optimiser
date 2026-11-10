# Task: Hex Route Optimiser for a Strava Territory Competition

> Brief for an AI coding agent. Work through the phases **in order**. Stop at each **🛑 Checkpoint** and wait for the human to confirm before continuing.

## 1. Context

We are a team in a competition. The competition website authenticates with Strava. The world is split into ~900 m hexagons. Any hexagon crossed during a recorded Strava activity is claimed for your team, and there is a team leaderboard.

We want a local tool that:

1. Shows which hexes we already cover, using our past Strava activities.
2. Plans runnable routes that claim the most valuable hexes within a distance budget.
3. Exports those routes as GPX files to load onto a watch or Strava.

**Environment:** macOS, Python 3.11+, run locally. There is no server and no deployment.

## 2. Hard constraints (do not violate)

- **No automated access to the competition website** unless the human explicitly confirms the competition rules allow it (see Phase 5). Until then, hex ownership data is entered manually or imported from a file.
- **Never commit secrets or personal data.** Strava tokens go in `.env`, which must be gitignored. Raw activity data stays in `data/`, which must also be gitignored.
- **Respect Strava API rate limits.** Cache responses locally and never re-fetch activities already downloaded.
- **Prefer the Strava bulk export** (GPX/FIT files from Strava's "Download your data") as the primary data source. Treat the API as optional.
- Keep it simple: a CLI plus generated HTML maps. No web app.

## 3. Proposed stack

| Purpose | Library |
|---|---|
| Hex grid | `h3` (v4 API) |
| Path network | `osmnx`, `networkx` |
| GPS parsing | `gpxpy`, `fitparse` |
| Geometry | `shapely` |
| Maps | `folium` |
| CLI | `typer` |
| Config | `python-dotenv`, a `config.toml` |
| Tests | `pytest` |

## 4. Repo layout

```
hexroute/
  README.md
  TASK.md              # this file
  pyproject.toml
  .env.example
  .gitignore           # .env, data/, out/, cache/
  config.toml          # home location, H3 resolution, distance budget
  data/                # bulk export goes here (gitignored)
  out/                 # maps + GPX (gitignored)
  src/hexroute/
    grid.py            # H3 helpers
    ingest.py          # parse GPX/FIT -> points
    coverage.py        # points -> hex set
    targets.py         # load/score target hexes
    graph.py           # OSM network download + caching
    optimise.py        # route search
    export.py          # GPX + folium output
    cli.py
  tests/
```

## 5. Phases

### Phase 0: Scaffold [COMPLETED ✓]
- Create the repo layout, `pyproject.toml`, `.gitignore`, `.env.example`, a README with setup steps, and a `hexroute --help` command.
- **Done when:** `pip install -e .` works and `hexroute --help` runs. (Completed & verified)

### Phase 1: Verify the hex grid ⚠️ assumption check [COMPLETED & CONFIRMED ✓]
We **assume** the competition uses H3 resolution 8 (cells ~920 m across). This must be verified before anything is built on it.
- Add `hexroute grid check --lat <lat> --lng <lng> --res 8`. It outputs `out/grid_check.html`, a folium map of that cell and its neighbours, so the human can compare it against the competition site.
- Make the resolution configurable in `config.toml`.
- 🛑 **Checkpoint:** The human confirms the hexes line up with the site. If they don't, stop and report. The rest of the plan needs rethinking. *(Confirmed by human: H3 resolution 8 aligns with competition cells)*

### Phase 2: Ingest activity history
- Parse every GPX and FIT file in `data/` into a list of `(activity_id, timestamp, lat, lng)` points.
- Handle files with no GPS data (e.g. treadmill runs) by skipping them with a warning.
- Cache parsed output (e.g. parquet or JSON) so later runs are fast.
- Optional and behind a flag: Strava API sync via OAuth, pulling `latlng` streams for new activities only.
- **Done when:** `hexroute ingest` prints the activity count, point count and date range. Include tests using a small fixture GPX.

### Phase 3: Coverage map
- Convert points to H3 cells and record, for each hex, the visit count, last visit date and which activities visited it.
- To avoid missing hexes the GPS track passes through between sparse points, densify the track (interpolate between consecutive points) before converting it to cells.
- `hexroute coverage` outputs `out/coverage.html`: hexes shaded by visit count, with a toggle for the raw tracks.
- **Done when:** The map visually matches the human's Strava heatmap.

### Phase 4: Targets and scoring
- `targets.py` loads a CSV of `h3_index,status` where status is `unclaimed`, `enemy` or `ours`. It also supports clicking hexes on a generated map and exporting a CSV, or the human can hand-edit the file.
- Scoring is configurable in `config.toml`. Defaults: enemy = 3, unclaimed = 2, ours = 0, plus a small bonus for hexes adjacent to existing territory.
- **Done when:** `hexroute targets show` renders scored hexes on a map.

### Phase 5: Ownership data from the competition site (gated)
- 🛑 **Do not start without explicit human confirmation that automated access is allowed by the competition rules.**
- If allowed, the human will supply the endpoint they found in browser dev tools and a session cookie via `.env`. Write a fetcher that calls the endpoint at most once per run, caches the response and converts it to the Phase 4 CSV format.
- If not allowed, skip this phase entirely. Manual CSV entry remains the workflow.

### Phase 6: Route optimiser (core work)
This is an **orienteering problem**: maximise the total hex score collected on a route within a distance budget, starting and ending at a given point.
- `graph.py` downloads the OSM walking network around the start point using `osmnx`, with the radius set to half the budget. Cache the graph to disk.
- For each node or edge, precompute which H3 cell(s) it lies in.
- Algorithm, starting simple:
  1. **Greedy baseline:** Repeatedly add the target hex with the best score-per-extra-metre that keeps the route within budget. Route between waypoints with the shortest path on the graph, placing each waypoint near the hex **centre** rather than the edges.
  2. **Improvement:** Apply 2-opt reordering plus insert/remove local search. Count every hex the actual path crosses, not just the targets.
  3. Optionally favour edges used in past activities (from Phase 3) as "known runnable".
- Inputs: start lat/lng, budget in km, loop or one-way, and the scoring config.
- `hexroute plan --km 10 --loop` outputs `out/route.gpx`, `out/route.html` (route plus scored hexes) and a summary of distance, hexes claimed and score.
- **Done when:** The route is a continuous path on real footpaths or roads, stays within budget (±5%), and beats the greedy baseline score in tests on a synthetic graph.

### Phase 7: Polish
- Generate several alternative routes (top N).
- Add a "safety margin" option that skips hexes the route would only clip by less than 50 m.
- Update the README with usage examples.

## 6. Out of scope
- Hosting, user accounts, or a multi-user web UI.
- Anything that posts activities to Strava or interacts with the competition site beyond read-only access in Phase 5.
- Real-time or live tracking.

## 7. Open questions for the human
1. Does the hex grid match H3 resolution 8? (Answered in Phase 1.)
2. Do the competition rules permit scripted access to the site?
3. Does a hex need to be crossed by the track, or is any GPS point inside it enough?
4. Do claims expire or get stolen over time, and should the optimiser favour recently lost hexes?
5. What are the start points and typical distance budgets for each team member?
