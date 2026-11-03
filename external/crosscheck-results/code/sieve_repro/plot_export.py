"""Deterministic PNG, SVG and PDF export helpers for measured-result plots."""

from pathlib import Path

import matplotlib


def save_figure_exports(fig, root: Path, basename: str, *, dpi: int = 220) -> list[Path]:
    """Write raster and vector plots without timestamps or random SVG element IDs."""
    matplotlib.rcParams["svg.hashsalt"] = "sieve-reproduction-fixed-v1"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for extension in ("png", "svg", "pdf"):
        path = root / f"{basename}.{extension}"
        options = {"dpi": dpi, "bbox_inches": "tight"}
        if extension == "svg":
            options["metadata"] = {"Date": None}
        elif extension == "pdf":
            options["metadata"] = {"CreationDate": None, "ModDate": None}
        fig.savefig(path, **options)
        paths.append(path)
    return paths
