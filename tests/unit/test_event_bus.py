"""
Tests for ARCHON PRIME Event Bus
================================

Tests the async event-driven communication system.
"""

import pytest
import asyncio
from datetime import datetime, timezone

from archon_prime.core.event_bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
)


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def sample_event():
    """Create a sample event."""
    return Event(
        event_type=EventType.SIGNAL_GENERATED,
        data={"symbol": "EURUSD", "direction": 1},
        source="test_strategy",
    )


class TestEventCreation:
    """Tests for event creation."""

    def test_create_event(self, sample_event):
        """Should create event with required fields."""
        assert sample_event.event_type == EventType.SIGNAL_GENERATED
        assert sample_event.data["symbol"] == "EURUSD"
        assert sample_event.source == "test_strategy"
        assert sample_event.priority == EventPriority.NORMAL

    def test_event_has_timestamp(self, sample_event):
        """Event should have timestamp."""
        assert sample_event.timestamp is not None
        assert isinstance(sample_event.timestamp, datetime)

    def test_event_has_id(self, sample_event):
        """Event should have unique ID."""
        assert sample_event.event_id is not None
        assert sample_event.event_id.startswith("evt_")

    def test_event_to_dict(self, sample_event):
        """Should convert event to dictionary."""
        data = sample_event.to_dict()
        assert data["event_type"] == "SIGNAL_GENERATED"
        assert data["source"] == "test_strategy"
        assert "timestamp" in data


class TestSubscriptions:
    """Tests for event subscriptions."""

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self, event_bus, sample_event):
        """Should receive events after subscribing."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(
            "test_subscriber",
            {EventType.SIGNAL_GENERATED},
            handler,
        )

        await event_bus.publish_sync(sample_event)

        assert len(received) == 1
        assert received[0].data["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus, sample_event):
        """Should not receive events after unsubscribing."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe("test_sub", {EventType.SIGNAL_GENERATED}, handler)
        event_bus.unsubscribe("test_sub")

        await event_bus.publish_sync(sample_event)

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_filter_function(self, event_bus):
        """Should apply filter function to events."""
        received = []

        async def handler(event):
            received.append(event)

        def filter_eurusd(event):
            return event.data.get("symbol") == "EURUSD"

        event_bus.subscribe(
            "filtered_sub",
            {EventType.SIGNAL_GENERATED},
            handler,
            filter_func=filter_eurusd,
        )

        # Should pass filter
        await event_bus.publish_sync(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data={"symbol": "EURUSD"},
            source="test",
        ))

        # Should be filtered out
        await event_bus.publish_sync(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data={"symbol": "GBPUSD"},
            source="test",
        ))

        assert len(received) == 1
        assert received[0].data["symbol"] == "EURUSD"


class TestEventTypes:
    """Tests for event type filtering."""

    @pytest.mark.asyncio
    async def test_only_receive_subscribed_types(self, event_bus):
        """Should only receive subscribed event types."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe("sub", {EventType.ORDER_FILLED}, handler)

        # Should not receive
        await event_bus.publish_sync(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data={},
            source="test",
        ))

        # Should receive
        await event_bus.publish_sync(Event(
            event_type=EventType.ORDER_FILLED,
            data={},
            source="test",
        ))

        assert len(received) == 1
        assert received[0].event_type == EventType.ORDER_FILLED

    @pytest.mark.asyncio
    async def test_multiple_event_types(self, event_bus):
        """Should receive multiple subscribed event types."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(
            "multi_sub",
            {EventType.ORDER_FILLED, EventType.ORDER_CANCELLED},
            handler,
        )

        await event_bus.publish_sync(Event(
            event_type=EventType.ORDER_FILLED,
            data={},
            source="test",
        ))

        await event_bus.publish_sync(Event(
            event_type=EventType.ORDER_CANCELLED,
            data={},
            source="test",
        ))

        assert len(received) == 2


class TestEventHistory:
    """Tests for event history."""

    @pytest.mark.asyncio
    async def test_history_stored(self, event_bus, sample_event):
        """Should store event history."""
        await event_bus.publish_sync(sample_event)

        history = event_bus.get_history()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_history_filtered_by_type(self, event_bus):
        """Should filter history by event type."""
        await event_bus.publish_sync(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data={},
            source="test",
        ))
        await event_bus.publish_sync(Event(
            event_type=EventType.ORDER_FILLED,
            data={},
            source="test",
        ))

        signal_history = event_bus.get_history(event_type=EventType.SIGNAL_GENERATED)
        assert len(signal_history) == 1


class TestEventBusStats:
    """Tests for event bus statistics."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self, event_bus, sample_event):
        """Should track event statistics."""
        async def handler(event):
            pass

        event_bus.subscribe("sub", {EventType.SIGNAL_GENERATED}, handler)

        await event_bus.publish_sync(sample_event)

        stats = event_bus.get_stats()
        assert stats["events_published"] == 1
        assert stats["events_delivered"] == 1
        assert stats["subscribers"] == 1


class TestEventBusLifecycle:
    """Tests for event bus start/stop."""

    @pytest.mark.asyncio
    async def test_start_stop(self, event_bus):
        """Should start and stop cleanly."""
        await event_bus.start()
        assert event_bus._running

        await event_bus.stop()
        assert not event_bus._running
