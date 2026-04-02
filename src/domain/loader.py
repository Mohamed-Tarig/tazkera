from pathlib import Path

import yaml

from src.schemas.domain import DomainConfig

_cache: dict[str, DomainConfig] = {}


def load_domain_config(domain_id: str) -> DomainConfig:
    if domain_id in _cache:
        return _cache[domain_id]

    config_path = Path("configs") / f"{domain_id}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Domain config not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    config = DomainConfig(**raw)
    _cache[domain_id] = config
    return config


def get_available_domains() -> list[str]:
    configs_dir = Path("configs")
    return [
        f.stem
        for f in configs_dir.glob("*.yaml")
        if not f.stem.startswith("_")
    ]