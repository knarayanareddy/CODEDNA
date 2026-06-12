"""Event system for CodeDNA SSE streaming.

Implements pub-sub pattern for broadcasting job events to connected clients.
Per design spec: Real-time progress updates and build completion notifications.
"""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for SSE streaming."""
    JOB_QUEUED = "job.queued"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETE = "job.complete"
    JOB_FAILED = "job.failed"
    DAEMON_STATUS = "daemon.status"
    SCAN_COMPLETE = "scan.complete"
    BUILD_COMPLETE = "build.complete"


@dataclass
class Event:
    """Represents an event to be broadcast via SSE."""
    type: str
    data: dict
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            from datetime import datetime, timezone
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def to_sse_format(self) -> str:
        """Format event for SSE streaming."""
        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"


class EventBus:
    """
    Thread-safe event bus for publishing and subscribing to CodeDNA events.
    
    Uses asyncio for non-blocking event distribution to SSE clients.
    """
    
    _instance: Optional["EventBus"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._initialized = True
        logger.info("EventBus initialized")
    
    async def subscribe(self, event_types: Optional[List[str]] = None) -> asyncio.Queue:
        """
        Subscribe to events. Returns a queue that receives matching events.
        
        Args:
            event_types: List of event types to subscribe to. None = all events.
        
        Returns:
            asyncio.Queue that receives Event objects.
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        async with self._lock:
            if event_types is None:
                # Subscribe to all events
                self._subscribers["*"].append(queue)
            else:
                for event_type in event_types:
                    self._subscribers[event_type].append(queue)
        
        logger.debug(f"Subscribed to events: {event_types or 'all'}")
        return queue
    
    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe a queue from all events."""
        async with self._lock:
            for event_type, queues in list(self._subscribers.items()):
                if queue in queues:
                    queues.remove(queue)
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all matching subscribers.
        
        Args:
            event: Event to publish.
        """
        async with self._lock:
            # Get queues subscribed to this specific event type
            queues = list(self._subscribers.get(event.type, []))
            # Also notify wildcard subscribers
            queues.extend(self._subscribers.get("*", []))
        
        for queue in queues:
            try:
                await asyncio.wait_for(queue.put(event), timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning(f"Queue full, dropping event: {event.type}")
            except Exception as e:
                logger.error(f"Failed to deliver event {event.type}: {e}")
        
        logger.debug(f"Published event: {event.type}")
    
    def publish_sync(self, event: Event) -> None:
        """Synchronous publish for use outside async context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.publish(event))
            else:
                loop.run_until_complete(self.publish(event))
        except RuntimeError:
            # No event loop running
            pass
    
    async def broadcast_status(self) -> None:
        """Broadcast periodic daemon status update."""
        from codedna.db.schema import get_schema_version, list_tracked_repos
        from codedna.db.session import get_raw_connection
        from codedna.db.schema import CURRENT_SCHEMA_VERSION
        
        try:
            conn = get_raw_connection()
            db_version = get_schema_version(conn)
            repos = list_tracked_repos(conn)
            conn.close()
            
            event = Event(
                type=EventType.DAEMON_STATUS.value,
                data={
                    "status": "running",
                    "db_version": db_version,
                    "expected_schema_version": CURRENT_SCHEMA_VERSION,
                    "active_repos": len(repos),
                }
            )
            await self.publish(event)
        except Exception as e:
            logger.error(f"Failed to broadcast status: {e}")


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global EventBus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def emit_job_event(event_type: EventType, job_id: str, repo_id: str, **extra_data) -> None:
    """Convenience function to emit job-related events."""
    event = Event(
        type=event_type.value,
        data={
            "job_id": job_id,
            "repo_id": repo_id,
            **extra_data
        }
    )
    await get_event_bus().publish(event)


async def emit_scan_event(scan_id: str, repo_id: str, dna_score: float, file_path: str) -> None:
    """Convenience function to emit scan completion events."""
    event = Event(
        type=EventType.SCAN_COMPLETE.value,
        data={
            "scan_id": scan_id,
            "repo_id": repo_id,
            "dna_score": dna_score,
            "file_path": file_path,
        }
    )
    await get_event_bus().publish(event)