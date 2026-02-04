"""Base class for Kubernetes resource watchers.

Provides a generic watch loop that streams events from a K8s API list function
and delegates processing to subclasses.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable

from kubernetes import watch

import restart_controller


class Watcher(ABC):
    """Base class for Kubernetes event watchers.

    Provides the generic watch loop: creates a Watch stream, iterates events,
    and delegates processing to the subclass.
    """

    ANNOTATION_PARENT = f"{restart_controller.ANNOTATION_PREFIX}parent"

    def __init__(self, namespace: str, on_change: Callable[[str], None]) -> None:
        self._logger = logging.getLogger(type(self).__name__)
        self._namespace = namespace
        self._on_change = on_change

    @property
    @abstractmethod
    def _list_func(self) -> Callable[..., object]:
        """Return the K8s API list function to stream."""

    @abstractmethod
    def _process_event(self, event: dict) -> None:
        """Process a single watch event."""

    def watch(self) -> None:
        """Run the watch loop indefinitely, delegating events to _process_event."""
        w = watch.Watch()
        self._logger.info("Starting %s on namespace %s", type(self).__name__, self._namespace)
        for event in w.stream(self._list_func, namespace=self._namespace):
            self._process_event(event)

    @staticmethod
    def _get_annotations(obj: object) -> dict[str, str]:
        """Safely extract annotations from a K8s object."""
        metadata = getattr(obj, "metadata", None)
        if metadata is None:
            return {}
        return metadata.annotations or {}

    @staticmethod
    def _has_restart_annotations(annotations: dict[str, str]) -> bool:
        """Check if annotations contain any restart-controller keys."""
        return any(k.startswith(restart_controller.ANNOTATION_PREFIX) for k in annotations)
