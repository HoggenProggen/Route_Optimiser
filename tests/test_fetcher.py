"""Tests for competition site data parser and fetcher."""

from hexroute.fetcher import parse_competition_payload
from hexroute.targets import HexStatus


def test_parse_geojson_payload() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "h3": "88195da49bfffff",
                    "team": "Red Team",
                    "visits": 4,
                },
                "geometry": {"type": "Point", "coordinates": [-0.1278, 51.5074]},
            },
            {
                "type": "Feature",
                "properties": {
                    "h3": "88195da493fffff",
                    "team": "Blue Team",
                    "visits": 2,
                },
                "geometry": {"type": "Point", "coordinates": [-0.1378, 51.5174]},
            },
            {
                "type": "Feature",
                "properties": {
                    "h3": "88195da491fffff",
                    "team": None,
                },
                "geometry": {"type": "Point", "coordinates": [-0.1478, 51.5274]},
            },
        ],
    }

    # If our team is "Blue Team"
    ownership = parse_competition_payload(payload, our_team_name="Blue Team")
    assert len(ownership) == 3

    assert ownership["88195da49bfffff"].status == HexStatus.ENEMY
    assert ownership["88195da49bfffff"].owner_team == "Red Team"
    assert ownership["88195da49bfffff"].enemy_visits == 4
    assert ownership["88195da49bfffff"].visits_to_flip == 5  # Needs 5 to beat 4

    assert ownership["88195da493fffff"].status == HexStatus.OURS
    assert ownership["88195da493fffff"].owner_team == "Blue Team"

    assert ownership["88195da491fffff"].status == HexStatus.UNCLAIMED


def test_parse_json_dict_payload() -> None:
    payload = {
        "hexes": [
            {"cell": "88195da49bfffff", "owner": "Tigers", "visits": 1},
            {"cell": "88195da493fffff", "owner": "Lions", "visits": 3},
        ]
    }

    ownership = parse_competition_payload(payload, our_team_name="Tigers")
    assert ownership["88195da49bfffff"].status == HexStatus.OURS
    assert ownership["88195da493fffff"].status == HexStatus.ENEMY


def test_parse_strods_land_grab_payload() -> None:
    payload = {
        "week_start": "2026-11-09",
        "today": 1,
        "teams": [
            {"id": 28, "name": "Team Red", "colour": "#ff0000"},
            {"id": 29, "name": "Team Blue", "colour": "#0000ff"},
        ],
        "your_team": 1,
        "cells": ["88195da22dfffff", "88195da221fffff", "88195da22bfffff"],
        "activities": [
            {"team": 0, "minutes": 100, "cells": [0, 1], "athlete": "Alice"},
            {"team": 1, "minutes": 200, "cells": [1], "athlete": "Bob"},
            {"team": 1, "minutes": 300, "cells": [1], "athlete": "Charlie"},
        ],
    }

    ownership = parse_competition_payload(payload, our_team_name="Team Blue")
    assert len(ownership) == 3

    # Cell 0 was visited once by Team Red (team 0) -> Enemy
    assert ownership["88195da22dfffff"].status == HexStatus.ENEMY
    assert ownership["88195da22dfffff"].enemy_visits == 1
    assert ownership["88195da22dfffff"].visits_to_flip == 2

    # Cell 1 was visited by Alice (Red: 1), then Bob (Blue: 1 -> Red holds tie), then Charlie (Blue: 2 -> Blue wins)
    assert ownership["88195da221fffff"].status == HexStatus.OURS
    assert ownership["88195da221fffff"].our_visits == 2
    assert ownership["88195da221fffff"].enemy_visits == 1
    assert ownership["88195da221fffff"].visits_to_flip == 0

    # Cell 2 was never visited -> Unclaimed
    assert ownership["88195da22bfffff"].status == HexStatus.UNCLAIMED
    assert ownership["88195da22bfffff"].visits_to_flip == 1
