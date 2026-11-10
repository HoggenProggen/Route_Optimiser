"""Unit tests for the Hexroute interactive web UI and API server."""

import json
from http.server import HTTPServer
import threading
import urllib.request
from pathlib import Path
import pytest

from hexroute.server import HexrouteRequestHandler, get_ui_html


@pytest.fixture(scope="module")
def test_server():
    """Start an ephemeral test HTTP server on an available port."""
    server = HTTPServer(("127.0.0.1", 0), HexrouteRequestHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_get_ui_html():
    """Verify HTML single-page app generation contains key elements."""
    html = get_ui_html()
    assert "<!DOCTYPE html>" in html
    assert "Hexroute" in html
    assert "start-lat" in html
    assert "start-lng" in html
    assert "budget-input" in html
    assert "budget-slider" in html
    assert "exercise-mode" in html
    assert "leaflet" in html.lower()


def test_api_config(test_server):
    """Verify /api/config returns configured home location and defaults."""
    url = f"{test_server}/api/config"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "home_lat" in data
        assert "home_lng" in data
        assert "default_budget_km" in data
        assert "team_name" in data


def test_api_targets(test_server):
    """Verify /api/targets returns list of target hexes."""
    url = f"{test_server}/api/targets"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "targets" in data
        assert isinstance(data["targets"], list)


def test_api_index_html(test_server):
    """Verify GET / returns HTML application."""
    url = f"{test_server}/"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        assert "<title>Hexroute Optimiser" in content
