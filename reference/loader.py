from __future__ import annotations

from pathlib import Path

import yaml


def load_reference(model_name: str, reference_dir: str = "reference/models") -> dict:
    dir_path = Path(reference_dir)
    # Try exact filename first, then with common variations
    candidates = [
        dir_path / f"{model_name}.yaml",
        dir_path / f"{model_name.replace('-', '_')}.yaml",
    ]

    for path in candidates:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)

    # Try partial match
    for path in dir_path.glob("*.yaml"):
        stem = path.stem.lower()
        if model_name.lower() in stem or stem in model_name.lower():
            with open(path) as f:
                return yaml.safe_load(f)

    return {}


def list_available_models(reference_dir: str = "reference/models") -> list[str]:
    dir_path = Path(reference_dir)
    if not dir_path.exists():
        return []
    return sorted(p.stem for p in dir_path.glob("*.yaml"))
