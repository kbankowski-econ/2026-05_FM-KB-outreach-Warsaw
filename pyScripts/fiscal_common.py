from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_ENV_VAR = "FISCAL_CONFIG_PATH"


def get_config_path() -> Path:
    """Return the absolute path to the active fiscal configuration file."""
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path(__file__).resolve().with_name("fiscal_config.json")


def load_config() -> Dict[str, Any]:
    """Load the JSON configuration used across fiscal scripts."""
    config_path = get_config_path()
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_chart_config() -> Dict[str, Any]:
    """Load the chart-specific styling configuration."""
    config_path = Path(__file__).resolve().with_name("chartConfig.json")
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_output_path(config: Dict[str, Any]) -> Path:
    """Resolve the output directory specified in the configuration."""
    base_dir = get_config_path().parent
    relative_path = config["output_settings"]["base_path"]
    return (base_dir / relative_path).resolve()


def ensure_output_dir(config: Dict[str, Any]) -> Path:
    """Create (if needed) and return the configured output directory."""
    output_dir = resolve_output_path(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_project_root() -> Path:
    """Return the repository root for the FM conjunctural project."""
    return Path(__file__).resolve().parents[1]


def resolve_project_path(*path_segments: str) -> Path:
    """Build an absolute path inside the project root."""
    return get_project_root().joinpath(*path_segments)


def resolve_from_config(path_like: str) -> Path:
    """Resolve a path relative to the configuration file location."""
    return (get_config_path().parent / path_like).resolve()


_CM_TO_PX = 37.795275591  # 1 cm at 96 DPI


def get_chart_dims_px(png_filename: str) -> tuple[int, int]:
    """Return (width_px, height_px) for a chart by matching its PNG filename
    against chartTable.csv, which stores Height/Width in cm."""
    import csv

    csv_path = Path(__file__).resolve().with_name("chartTable.csv")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            png_field = row.get("pngFile", "")
            if png_field and Path(png_field).name == png_filename:
                width_cm = float(row["Width"])
                height_cm = float(row["Height"])
                return round(width_cm * _CM_TO_PX), round(height_cm * _CM_TO_PX)
    raise KeyError(f"{png_filename} not found in chartTable.csv")


def smart_save_image(fig: Any, output_path: Path, format: str = None) -> bool:
    """
    Save a Plotly figure only if the image content has changed.
    Format is inferred from file extension if not specified.
    Returns True if the file was updated, False if it was skipped.
    """
    import plotly.io as pio

    if format is None:
        format = Path(output_path).suffix.lstrip('.') or 'png'

    # Generate image bytes in memory (scale=2 for PNG parity with pio.write_image)
    scale = 2 if format == 'png' else 1
    new_image_bytes = pio.to_image(fig, format=format, scale=scale)

    # Check if file exists and compare
    if output_path.exists():
        with open(output_path, 'rb') as f:
            existing_bytes = f.read()
        if existing_bytes == new_image_bytes:
            print(f"  [SmartSave] Skipping {output_path.name} (no changes)")
            return False

    # Save to disk
    print(f"  [SmartSave] Updating {output_path.name}")
    with open(output_path, 'wb') as f:
        f.write(new_image_bytes)
    return True
