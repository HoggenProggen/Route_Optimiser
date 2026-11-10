"""Command-line interface for hexroute."""

from pathlib import Path
from typing import Optional
import typer

from hexroute.config import load_config
from hexroute.grid import generate_grid_check_map, latlng_to_cell

app = typer.Typer(
    name="hexroute",
    help="Hex Route Optimiser for Strava Territory Competitions.",
    no_args_is_help=True,
)

grid_app = typer.Typer(
    name="grid",
    help="Hex grid verification and inspection commands.",
    no_args_is_help=True,
)
app.add_typer(grid_app, name="grid")


@grid_app.command(name="check")
def grid_check(
    lat: Optional[float] = typer.Option(
        None,
        "--lat",
        help="Latitude of check point (defaults to home_lat in config.toml)",
    ),
    lng: Optional[float] = typer.Option(
        None,
        "--lng",
        help="Longitude of check point (defaults to home_lng in config.toml)",
    ),
    res: Optional[int] = typer.Option(
        None,
        "--res",
        help="H3 resolution (defaults to h3_resolution in config.toml, usually 8)",
    ),
    ring: int = typer.Option(
        1,
        "--ring",
        help="Neighbor ring depth to render around center cell (default: 1)",
    ),
    out: Optional[str] = typer.Option(
        None,
        "--out",
        help="Output HTML map path (defaults to out/grid_check.html)",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom config.toml file",
    ),
) -> None:
    """
    Generate an HTML map of the H3 cell at (lat, lng) and its neighbors.
    Use this to visually verify that H3 resolution matches the competition site grid.
    """
    cfg = load_config(config)

    target_lat = lat if lat is not None else float(cfg["general"]["home_lat"])
    target_lng = lng if lng is not None else float(cfg["general"]["home_lng"])
    target_res = res if res is not None else int(cfg["general"]["h3_resolution"])

    out_dir = Path(cfg["paths"]["out_dir"])
    target_out = Path(out) if out is not None else out_dir / "grid_check.html"

    cell = latlng_to_cell(target_lat, target_lng, target_res)
    typer.echo(f"Checking H3 cell for lat={target_lat}, lng={target_lng} (res={target_res})...")
    typer.echo(f"Center H3 Index: {cell}")

    output_file = generate_grid_check_map(
        lat=target_lat,
        lng=target_lng,
        res=target_res,
        ring=ring,
        out_path=target_out,
    )

    typer.secho(f"✓ Grid check map generated at: {output_file}", fg=typer.colors.GREEN, bold=True)
    typer.echo("Open this file in your browser to verify cell boundaries against the competition site.")


@app.command(name="info")
def info(
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom config.toml file",
    ),
) -> None:
    """Display current configuration and workspace status."""
    cfg = load_config(config)
    typer.echo("=== Hexroute Configuration ===")
    typer.echo(f"H3 Resolution:     {cfg['general']['h3_resolution']}")
    typer.echo(f"Home Coordinates:  {cfg['general']['home_lat']}, {cfg['general']['home_lng']}")
    typer.echo(f"Default Budget:    {cfg['general']['default_budget_km']} km")
    typer.echo(f"Data Directory:    {cfg['paths']['data_dir']}")
    typer.echo(f"Output Directory:  {cfg['paths']['out_dir']}")
    typer.echo(f"Cache Directory:   {cfg['paths']['cache_dir']}")


if __name__ == "__main__":
    app()
