from __future__ import annotations

from typing import Any

_registry: dict[str, dict[str, type]] = {
    "ingestor": {},
    "dedup": {},
    "llm": {},
    "validator": {},
    "sink": {},
}


def register(plugin_type: str, name: str, cls: type) -> None:
    """Register a plugin class under the given type and name."""
    if plugin_type not in _registry:
        raise KeyError(
            f"Unknown plugin type '{plugin_type}'. Valid types: {list(_registry.keys())}"
        )
    _registry[plugin_type][name] = cls


def get(plugin_type: str, name: str) -> type:
    """Get a plugin class by type and name. Raises KeyError if not found."""
    if name not in _registry.get(plugin_type, {}):
        available = list(_registry.get(plugin_type, {}).keys())
        raise KeyError(f"Plugin '{name}' not found in type '{plugin_type}'. Available: {available}")
    return _registry[plugin_type][name]


def get_instance(plugin_type: str, name: str, **kwargs: Any) -> Any:
    """Instantiate a plugin by type and name, passing optional kwargs to __init__."""
    cls = get(plugin_type, name)
    return cls(**kwargs) if kwargs else cls()


def list_available(plugin_type: str) -> list[str]:
    """Return all registered plugin names for a given type."""
    return list(_registry.get(plugin_type, {}).keys())
