# ARCHON_FEAT: event-bus-001
"""
ARCHON PRIME - Event Bus
========================

Async event-driven communication system for plugin coordination.

Features:
- Pub/sub pattern for loose coupling
- Priority-based event handling
- Event filtering and routing
- Dead letter queue for failed events

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger("ARCHON_EventBus")


class EventType(Enum):
    """Event types for the trading system."""

    # Market events
    TICK = auto()
    BAR = auto()
    QUOTE = auto()

    # Signal events
    SIGNAL_GENERATED = auto()
    SIGNAL_APPROVED = auto()
    SIGNAL_REJECTED = auto()

    # Order events
    ORDER_SUBMIT = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELLED = auto()
    ORDER_REJECTED = auto()
    ORDER_MODIFIED = auto()

    # Position events
    POSITION_OPENED = auto()
    POSITION_CLOSED = auto()
    POSITION_UPDATED = auto()

    # Risk events
    RISK_ALERT = auto()
    DRAWDOWN_WARNING = auto()
    DRAWDOWN_HALT = auto()
    PANIC_HEDGE = auto()

    # System events
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    SYSTEM_ERROR = auto()
    PLUGIN_LOADED = auto()
    PLUGIN_UNLOADED = auto()

    # Data events
    DATA_UPDATE = auto()
    NEWS_EVENT = auto()
    CALENDAR_EVENT = auto()

    # Monitoring events
    HEARTBEAT = auto()
    METRICS_UPDATE = auto()
    HEALTH_CHECK = auto()


class EventPriority(Enum):
    """Event processing priority."""

    CRITICAL = 0  # Risk/panic events
    HIGH = 1      # Order events
    NORMAL = 2    # Signal events
    LOW = 3       # Metrics/monitoring


@dataclass
class Event:
    """Event message for the event bus."""

    event_type: EventType
    data: Dict[str, Any]
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: EventPriority = EventPriority.NORMAL
    event_id: str = field(default_factory=lambda: f"evt_{datetime.now().timestamp()}")
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.name,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.name,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
        }


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


@dataclass
class Subscription:
    """Event subscription."""

    handler: EventHandler
    subscriber_id: str
    event_types: Set[EventType]
    filter_func: Optional[Callable[[Event], bool]] = None
    priority: int = 0


class EventBus:
    """
    Async event bus for plugin communication.

    Provides pub/sub messaging between plugins with:
    - Priority-based event queues
    - Event filtering
    - Dead letter queue for failures
    - Event history for debugging

    Example:
        bus = EventBus()

        async def handle_signal(event: Event):
            print(f"Signal received: {event.data}")

        bus.subscribe("strategy_1", {EventType.SIGNAL_GENERATED}, handle_signal)

        await bus.publish(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data={"symbol": "EURUSD", "direction": 1},
            source="signal_gate"
        ))
    """

    def __init__(self, max_queue_size: int = 10000, history_size: int = 1000):
        self._subscriptions: Dict[str, Subscription] = {}
        self._type_index: Dict[EventType, Set[str]] = defaultdict(set)
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._dead_letter: List[Event] = []
        self._history: List[Event] = []
        self._history_size = history_size
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._event_counter: int = 0  # Tie-breaker for priority queue
        self._stats = {
            "events_published": 0,
            "events_delivered": 0,
            "events_failed": 0,
        }

        logger.info("EventBus initialized")

    def subscribe(
        self,
        subscriber_id: str,
        event_types: Set[EventType],
        handler: EventHandler,
        filter_func: Optional[Callable[[Event], bool]] = None,
        priority: int = 0,
    ) -> None:
        """
        Subscribe to events.

        Args:
            subscriber_id: Unique subscriber identifier
            event_types: Set of event types to subscribe to
            handler: Async handler function
            filter_func: Optional filter function
            priority: Handler priority (lower = higher priority)
        """
        subscription = Subscription(
            handler=handler,
            subscriber_id=subscriber_id,
            event_types=event_types,
            filter_func=filter_func,
            priority=priority,
        )

        self._subscriptions[subscriber_id] = subscription

        for event_type in event_types:
            self._type_index[event_type].add(subscriber_id)

        logger.debug(f"Subscription added: {subscriber_id} -> {[e.name for e in event_types]}")

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscription."""
        if subscriber_id not in self._subscriptions:
            return False

        subscription = self._subscriptions.pop(subscriber_id)

        for event_type in subscription.event_types:
            self._type_index[event_type].discard(subscriber_id)

        logger.debug(f"Subscription removed: {subscriber_id}")
        return True

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.

        Args:
            event: Event to publish
        """
        # Add to history
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

        # Queue for processing with counter as tie-breaker
        self._event_counter += 1
        await self._queue.put((event.priority.value, self._event_counter, event))
        self._stats["events_published"] += 1

        logger.debug(f"Event published: {event.event_type.name} from {event.source}")

    async def publish_sync(self, event: Event) -> int:
        """
        Publish and process event synchronously.

        Returns:
            Number of handlers that processed the event
        """
        # Add to history
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

        self._stats["events_published"] += 1

        return await self._dispatch_event(event)

    async def _dispatch_event(self, event: Event) -> int:
        """Dispatch event to matching subscribers."""
        subscriber_ids = self._type_index.get(event.event_type, set())
        handlers_called = 0

        # Sort by priority
        sorted_subs = sorted(
            [(sid, self._subscriptions[sid]) for sid in subscriber_ids if sid in self._subscriptions],
            key=lambda x: x[1].priority
        )

        for subscriber_id, subscription in sorted_subs:
            # Apply filter
            if subscription.filter_func and not subscription.filter_func(event):
                continue

            try:
                await subscription.handler(event)
                handlers_called += 1
                self._stats["events_delivered"] += 1
            except Exception as e:
                logger.error(f"Handler error for {subscriber_id}: {e}")
                self._dead_letter.append(event)
                self._stats["events_failed"] += 1

        return handlers_called

    async def start(self) -> None:
        """Start the event bus worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the event bus worker."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("EventBus stopped")

    async def _worker(self) -> None:
        """Background worker for processing events."""
        while self._running:
            try:
                priority, counter, event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            **self._stats,
            "subscribers": len(self._subscriptions),
            "queue_size": self._queue.qsize(),
            "dead_letter_count": len(self._dead_letter),
            "history_size": len(self._history),
        }

    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get event history, optionally filtered by type."""
        events = self._history

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def clear_dead_letter(self) -> List[Event]:
        """Clear and return dead letter queue."""
        events = self._dead_letter.copy()
        self._dead_letter.clear()
        return events


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "EventType",
    "EventPriority",
    "Event",
    "EventHandler",
    "Subscription",
    "EventBus",
]
