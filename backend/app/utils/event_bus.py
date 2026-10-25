"""
Module: event_bus.py
Purpose: Thread-safe, asynchronous In-Memory Event Bus for real-time Server-Sent Events (SSE).
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 3 (Low Code & High Signal),
           Rule 5 (Production Reliability & Zero Memory Leaks).
"""
import asyncio
import logging
import threading
import time
from typing import Dict, Set, Optional, Any, List
from collections import defaultdict, deque

logger = logging.getLogger("event_bus")

class EventBus:
    """
    Central Pub/Sub Event Bus supporting asynchronous event streaming (SSE).
    Allows publishing from both sync (worker threads) and async contexts safely.
    Maintains a rolling ring buffer of recent events for instant client hydration.
    """
    def __init__(self, history_limit: int = 30):
        # topic -> set of asyncio.Queue
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # topic -> deque of recent events
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_limit))
        # threading.Lock used for publish() (called from sync worker threads too)
        self._lock = threading.Lock()
        # asyncio.Lock used only in async subscribe/unsubscribe
        self._async_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Registers the main running event loop for cross-thread sync publishing."""
        self._loop = loop

    def get_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        if self._loop and self._loop.is_running():
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    async def subscribe(self, topic: str = "global") -> asyncio.Queue:
        """
        Subscribes a client to a specific topic or wildcard topic.
        Returns an asyncio.Queue that receives new events.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._async_lock:
            self._subscribers[topic].add(queue)
            logger.debug(f"Client subscribed to topic '{topic}'. Active subscribers: {len(self._subscribers[topic])}")
        return queue

    async def unsubscribe(self, topic: str, queue: asyncio.Queue):
        """Removes a subscriber queue to prevent memory leaks."""
        async with self._async_lock:
            if topic in self._subscribers and queue in self._subscribers[topic]:
                self._subscribers[topic].remove(queue)
                if not self._subscribers[topic]:
                    del self._subscribers[topic]
                logger.debug(f"Client unsubscribed from topic '{topic}'.")

    def get_recent_events(self, topic: str) -> List[Dict[str, Any]]:
        """Returns recent cached events for a topic to hydrate new SSE connections."""
        return list(self._history[topic])

    def publish(self, topic: str, event_type: str, data: Dict[str, Any]):
        """
        Thread-safe publish method. Can be called from synchronous or asynchronous code.
        Delivers the event to all subscribers of the specific topic and the wildcard/all topic.
        """
        now = time.strftime("%H:%M:%S")
        event = {
            "topic": topic,
            "event": event_type,
            "data": data,
            "timestamp": now,
        }

        # Store in rolling history buffer
        self._history[topic].append(event)
        if topic != "all":
            self._history["all"].append(event)

        # Broadcast to topic subscribers and 'all' subscribers
        targets = []
        # Use threading.Lock (non-async) so this is safe from any thread context
        with self._lock:
            if topic in self._subscribers:
                targets.extend(list(self._subscribers[topic]))
            if "all" in self._subscribers and topic != "all":
                targets.extend(list(self._subscribers["all"]))

        if not targets:
            return

        loop = self.get_event_loop()
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        for q in targets:
            try:
                # If queue is full, discard oldest to avoid backpressure hanging
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                
                # If we are already executing inside the target event loop, put directly
                if current_loop and loop and current_loop == loop:
                    q.put_nowait(event)
                elif loop and loop.is_running():
                    loop.call_soon_threadsafe(q.put_nowait, event)
                else:
                    q.put_nowait(event)
            except Exception as e:
                logger.warning(f"Failed to deliver event to subscriber on {topic}: {e}")

# Global singleton event bus
event_bus = EventBus()

def emit_event(topic: str, event_type: str, data: Dict[str, Any]):
    """Convenience helper to emit an event from anywhere in the codebase."""
    event_bus.publish(topic=topic, event_type=event_type, data=data)
