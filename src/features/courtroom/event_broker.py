"""Thread-safe in-memory event broker for courtroom trial events."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any
import asyncio


@dataclass
class CourtroomEventSubscription:
    """Active websocket subscription for a courtroom analysis."""

    analysis_id: str
    queue: asyncio.Queue[dict[str, Any]]
    loop: asyncio.AbstractEventLoop


class CourtroomEventBroker:
    """Broadcasts persisted trial events to websocket subscribers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscriptions: dict[str, list[CourtroomEventSubscription]] = {}

    def subscribe(
        self,
        analysis_id: str,
        queue: asyncio.Queue[dict[str, Any]],
        loop: asyncio.AbstractEventLoop,
    ) -> CourtroomEventSubscription:
        """Register a websocket subscriber for an analysis."""
        subscription = CourtroomEventSubscription(
            analysis_id=analysis_id,
            queue=queue,
            loop=loop,
        )
        with self._lock:
            self._subscriptions.setdefault(analysis_id, []).append(subscription)
        return subscription

    def unsubscribe(self, subscription: CourtroomEventSubscription) -> None:
        """Remove a websocket subscriber."""
        with self._lock:
            subs = self._subscriptions.get(subscription.analysis_id)
            if not subs:
                return
            self._subscriptions[subscription.analysis_id] = [
                item for item in subs if item is not subscription
            ]
            if not self._subscriptions[subscription.analysis_id]:
                self._subscriptions.pop(subscription.analysis_id, None)

    def publish(self, analysis_id: str, event: dict[str, Any]) -> None:
        """Push one event to all active subscribers for the analysis."""
        with self._lock:
            subs = list(self._subscriptions.get(analysis_id, []))

        for subscription in subs:
            subscription.loop.call_soon_threadsafe(
                subscription.queue.put_nowait, event
            )
