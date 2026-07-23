"""
Event System
============
Handles session events, listeners, and callbacks.
Supports cooperative cancellation and turn coordination.
"""

from typing import Callable, List, Dict, Any
import asyncio


class SessionEvent:
    """
    Represents a session event.
    """

    def __init__(self, event_type: str, data: Dict[str, Any] = None):
        """
        Initialize event.
        
        Args:
            event_type: Type of event (e.g., 'turn_start', 'turn_complete', 'tool_call')
            data: Event data
        """
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = asyncio.get_event_loop().time()

    def __repr__(self) -> str:
        return f"SessionEvent(type={self.event_type}, data={self.data})"


class EventBus:
    """
    Central event bus for session events.
    Manages listeners and event dispatch.
    """

    def __init__(self):
        """Initialize event bus."""
        self.listeners: Dict[str, List[Callable]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()

    def subscribe(self, event_type: str, handler: Callable):
        """
        Subscribe to events.
        
        Args:
            event_type: Event type to listen for
            handler: Callback function
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        """
        Unsubscribe from events.
        
        Args:
            event_type: Event type
            handler: Handler to remove
        """
        if event_type in self.listeners:
            self.listeners[event_type].remove(handler)

    async def emit(self, event: SessionEvent):
        """
        Emit event to all listeners.
        
        Args:
            event: SessionEvent to emit
        """
        await self.event_queue.put(event)
        
        handlers = self.listeners.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"[EventBus] Handler error: {e}")

    async def wait_for(self, event_type: str, timeout: float = None) -> SessionEvent:
        """
        Wait for specific event type.
        
        Args:
            event_type: Event type to wait for
            timeout: Timeout in seconds
            
        Returns:
            SessionEvent
            
        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        # TODO: Implement event filtering and waiting
        pass


class CancellationManager:
    """
    Manages cooperative cancellation of ongoing operations.
    Ensures queue consistency and graceful transition.
    """

    def __init__(self):
        """Initialize cancellation manager."""
        self.cancel_event = asyncio.Event()
        self.active_task: asyncio.Task = None
        self.lock = asyncio.Lock()

    async def request_cancel(self):
        """
        Request cancellation of current operation.
        Cooperative: waits for current operation to complete gracefully.
        """
        async with self.lock:
            self.cancel_event.set()
            if self.active_task and not self.active_task.done():
                self.active_task.cancel()

    def should_cancel(self) -> bool:
        """
        Check if cancellation was requested.
        
        Returns:
            True if cancellation requested
        """
        return self.cancel_event.is_set()

    async def reset(self):
        """
        Reset cancellation state for next operation.
        """
        async with self.lock:
            self.cancel_event.clear()
            self.active_task = None

    async def set_active_task(self, task: asyncio.Task):
        """
        Track active task for cancellation.
        
        Args:
            task: Task to track
        """
        async with self.lock:
            self.active_task = task
