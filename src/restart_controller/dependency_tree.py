"""Dependency tree logic for restart synchronization.

Stores parent-child relationships between deployments and pre-computes
descendants for efficient restart set calculation.
"""

from __future__ import annotations

import logging


class DependencyTree:
    """A tree of deployment dependencies with pre-computed descendants.

    Each deployment may have at most one parent and zero or more children.
    Descendants are computed eagerly so that lookups are O(1).
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(type(self).__name__)
        self._children: dict[str, set[str]] = {}
        self._descendants: dict[str, frozenset[str]] = {}

    def add(self, parent: str, children: list[str]) -> None:
        """Register a parent and its direct children, then recompute descendants."""
        self._children.setdefault(parent, set()).update(children)
        self._recompute()

    def get_children(self, deployment: str) -> set[str]:
        """Return direct children of a deployment."""
        return set(self._children.get(deployment, set()))

    def get_descendants(self, deployment: str) -> frozenset[str]:
        """Return all transitive descendants of a deployment (pre-computed)."""
        return self._descendants.get(deployment, frozenset())

    def compute_restart_set(self, triggers: set[str]) -> set[str]:
        """Compute the deduplicated set of deployments to restart.

        A triggered deployment causes all its descendants to restart.
        Descendants that are themselves triggers are excluded (they already restarted).

        Args:
            triggers: Set of deployment names that triggered a restart.

        Returns:
            Set of deployment names that should be restarted.
        """
        to_restart: set[str] = set()
        for trigger in triggers:
            to_restart.update(self.get_descendants(trigger) - triggers)

        self._logger.debug("Triggers: %s -> restart set: %s", triggers, to_restart)
        return to_restart

    def _recompute(self) -> None:
        """Pre-compute descendants for every known node."""
        self._descendants.clear()
        all_nodes: set[str] = set()
        for parent, children in self._children.items():
            all_nodes.add(parent)
            all_nodes.update(children)
        for node in all_nodes:
            self._descendants[node] = self._collect_descendants(node)

    def _collect_descendants(self, node: str) -> frozenset[str]:
        if node in self._descendants:
            return self._descendants[node]
        result: set[str] = set()
        for child in self._children.get(node, []):
            result.add(child)
            result.update(self._collect_descendants(child))
        return frozenset(result)
