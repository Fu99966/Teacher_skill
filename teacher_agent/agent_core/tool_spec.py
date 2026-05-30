"""ToolSpec – strong typing for tools + upgraded ToolRegistry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    required_context_keys: list[str] = field(default_factory=list)
    produced_context_keys: list[str] = field(default_factory=list)
    retryable: bool = False
    critical: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_context_keys": self.required_context_keys,
            "produced_context_keys": self.produced_context_keys,
            "retryable": self.retryable,
            "critical": self.critical,
        }


ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}
        self._specs: dict[str, ToolSpec] = {}

    def register(self, name: str, func: ToolFn, spec: ToolSpec | None = None) -> None:
        self._tools[name] = func
        if spec is not None:
            self._specs[name] = spec

    def get(self, name: str) -> ToolFn:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def get_spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def check_context(self, name: str, context: dict[str, Any]) -> list[str]:
        """Return list of missing required context keys."""
        spec = self._specs.get(name)
        if spec is None:
            return []
        return [k for k in spec.required_context_keys if k not in context]

    def validate_produced(self, name: str, context: dict[str, Any]) -> list[str]:
        """Return list of produced keys still missing from context."""
        spec = self._specs.get(name)
        if spec is None:
            return []
        return [k for k in spec.produced_context_keys if k not in context]

    def list_tools(self) -> list[dict[str, Any]]:
        result = []
        for name in self._tools:
            if name in self._specs:
                result.append(self._specs[name].to_dict())
            else:
                result.append({"name": name})
        return result
