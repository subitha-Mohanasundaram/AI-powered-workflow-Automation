"""
Plugin Manager Service — discovers and manages action plugins.

Plugins live in the `plugins/` directory at the project root.
Built-in plugins are auto-loaded on first use.
"""
import importlib
import os
import sys
from typing import Optional

from ..logging_config import get_logger

logger = get_logger(__name__)

# Registry: action_name -> BasePlugin instance
_plugin_registry: dict = {}
_loaded = False


def _ensure_plugins_in_path():
    """Add the project root to sys.path so plugin imports work."""
    # Project root is 4 levels up from this file:
    # backend/app/services/plugin_manager.py -> backend/app/services -> backend/app -> backend -> root
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(this_dir)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def load_plugins() -> dict:
    """
    Import all built-in plugins and register them by action name.
    Returns the full registry dict: {action_name: plugin_instance}.
    """
    global _plugin_registry, _loaded
    if _loaded:
        return _plugin_registry

    _ensure_plugins_in_path()

    builtin_modules = [
        "plugins.builtin.api_fetch_plugin",
        "plugins.builtin.report_plugin",
        "plugins.builtin.delivery_plugin",
    ]

    for module_path in builtin_modules:
        try:
            module = importlib.import_module(module_path)
            # Find the first BasePlugin subclass in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr.__name__ != "BasePlugin"
                    and hasattr(attr, "supported_actions")
                    and hasattr(attr, "plugin_id")
                    and attr.plugin_id
                ):
                    instance = attr()
                    for action in instance.supported_actions:
                        _plugin_registry[action] = instance
                    logger.info(
                        "Plugin loaded | id=%s | actions=%s",
                        instance.plugin_id,
                        instance.supported_actions,
                    )
        except Exception as exc:
            logger.warning("Failed to load plugin module %s | error=%s", module_path, exc)

    _loaded = True
    logger.info("Plugin loading complete | registered_actions=%d", len(_plugin_registry))
    return _plugin_registry


def get_plugin(action: str):
    """Return the plugin that handles the given action, or None."""
    registry = load_plugins()
    return registry.get(action)


def list_plugins() -> list[dict]:
    """Return a list of all registered plugins with their metadata."""
    registry = load_plugins()
    seen: set = set()
    result = []
    for action, plugin in registry.items():
        if plugin.plugin_id not in seen:
            seen.add(plugin.plugin_id)
            result.append({
                "plugin_id": plugin.plugin_id,
                "display_name": plugin.display_name,
                "supported_actions": plugin.supported_actions,
                "is_builtin": True,
            })
    return result
