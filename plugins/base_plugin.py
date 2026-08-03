"""
Base plugin abstract class.
All plugins must inherit from BasePlugin and implement `execute`.
"""
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """Abstract base class for all action plugins."""

    plugin_id: str = ""
    display_name: str = ""
    supported_actions: list[str] = []

    @abstractmethod
    def execute(self, action: str, params: dict, context: dict) -> dict:
        """
        Execute the given action with the supplied params and context.

        Args:
            action: The action name (must be in supported_actions)
            params: Action-specific parameters
            context: Shared execution context (workflow payload, user info, etc.)

        Returns:
            dict with at minimum {"status": "success"|"failed", "result": ...}
        """
        ...

    def supports(self, action: str) -> bool:
        """Return True if this plugin supports the given action."""
        return action in self.supported_actions

    def __repr__(self) -> str:
        return f"<Plugin {self.plugin_id!r} actions={self.supported_actions}>"
