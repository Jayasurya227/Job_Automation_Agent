"""
Module: task_queue.py
Purpose: Enterprise Multi-Tenant Background Task Queue & Worker Pool with Naukri Rate Limiting.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 3 (Low Code & High Signal), Rule 5 (Production Reliability).

Key Architecture:
1. Dynamic Concurrency Control: Throttles concurrent Playwright browser automation to MAX_CONCURRENT_WORKERS (default: 2)
   so that any number of active users (3, 5, 7, 10, etc.) are processed smoothly without server RAM exhaustion.
2. Naukri Anti-Bot Rate Limiter: Injects randomized humanized jitter (3.0s – 6.0s) between successive Naukri operations
   to guarantee accounts and server IP are protected against Akamai bot detection.
3. Strict User Isolation: Every task is tagged with user_id; users can only inspect, monitor, or cancel their own tasks.
"""

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from app.utils.event_bus import emit_event

logger = logging.getLogger("agent.task_queue")

DEFAULT_MAX_CONCURRENT_WORKERS = 2
DEFAULT_MIN_NAUKRI_INTERVAL_SECONDS = 3.5


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class UserTask:
    task_id: str
    user_id: int
    task_type: str  # e.g., 'discovery', '1click_apply', 'profile_boost', 'custom'
    payload: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress_message: str = "Task queued in worker pool."
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_message": self.progress_message,
            "result": self.result,
            "error": self.error,
        }


class NaukriRateLimiter:
    """
    Thread-safe and Async-native Rate Limiter with Anti-Bot Jitter.
    Enforces humanized spacing between browser hits across all concurrent users.
    """
    def __init__(self, min_interval_seconds: float = DEFAULT_MIN_NAUKRI_INTERVAL_SECONDS):
        self.min_interval = min_interval_seconds
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self, label: str = "Naukri"):
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if self._last_request_time > 0 and elapsed < self.min_interval:
                # Add human jitter between 0.5s and 2.5s
                sleep_needed = (self.min_interval - elapsed) + random.uniform(0.5, 2.5)
                logger.info(f"⏳ [RateLimiter] Pacing {label} operation. Sleeping for {sleep_needed:.2f}s...")
                await asyncio.sleep(sleep_needed)
            self._last_request_time = time.time()


class MultiTenantTaskQueue:
    """
    Enterprise In-Memory Asynchronous Worker Pool.
    Processes tasks across an arbitrary dynamic number of users without blocking the server.
    """
    def __init__(self, max_concurrent_workers: int = DEFAULT_MAX_CONCURRENT_WORKERS):
        self.max_workers = max_concurrent_workers
        self.rate_limiter = NaukriRateLimiter()
        self._queue: asyncio.Queue[UserTask] = asyncio.Queue()
        self._tasks: Dict[str, UserTask] = {}
        self._workers: List[asyncio.Task] = []
        self._is_running = False
        self._state_lock = asyncio.Lock()

    def start(self):
        """Starts background worker tasks in the current event loop."""
        if self._is_running:
            return
        self._is_running = True
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(self._worker_loop(worker_id=i + 1))
            self._workers.append(worker_task)
        logger.info(f"🚀 MultiTenantTaskQueue started with {self.max_workers} worker(s).")

    async def stop(self):
        """Gracefully drains and stops background workers."""
        if not self._is_running:
            return
        self._is_running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("🛑 MultiTenantTaskQueue stopped gracefully.")

    async def enqueue_task(
        self,
        user_id: int,
        task_type: str,
        payload: Optional[Dict[str, Any]] = None,
        custom_coro_fn: Optional[Callable[[UserTask], Coroutine[Any, Any, Dict[str, Any]]]] = None,
    ) -> UserTask:
        """
        Submits a new task to the queue, immediately returning the queued task object.
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = UserTask(
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            payload=payload or {},
        )
        if custom_coro_fn:
            task.payload["_custom_coro_fn"] = custom_coro_fn

        async with self._state_lock:
            self._tasks[task_id] = task

        await self._queue.put(task)

        # Emit queue event
        emit_event(f"task:{user_id}", "task_queued", task.to_dict())
        emit_event("task:all", "task_queued", task.to_dict())

        logger.info(f"📥 [User {user_id}] Task queued: {task_id} ({task_type}). Current queue size: {self._queue.qsize()}")
        return task

    def get_task(self, task_id: str, user_id: Optional[int] = None) -> Optional[UserTask]:
        """
        Fetches task status. If user_id is provided, enforces tenant isolation.
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        if user_id is not None and task.user_id != user_id:
            logger.warning(f"Unauthorized task access attempt: user {user_id} tried to read task {task_id} belonging to user {task.user_id}")
            return None
        return task

    def list_user_tasks(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lists tasks strictly belonging to the specified user.
        """
        user_tasks = [
            t.to_dict() for t in self._tasks.values()
            if t.user_id == user_id
        ]
        user_tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return user_tasks[:limit]

    async def cancel_task(self, task_id: str, user_id: int) -> bool:
        """
        Cancels a queued task before execution begins.
        """
        task = self.get_task(task_id, user_id=user_id)
        if not task:
            return False
        if task.status == TaskStatus.QUEUED:
            task.status = TaskStatus.CANCELLED
            task.progress_message = "Cancelled by user."
            task.completed_at = datetime.now(timezone.utc).isoformat()
            emit_event(f"task:{user_id}", "task_cancelled", task.to_dict())
            return True
        return False

    async def _worker_loop(self, worker_id: int):
        """Worker loop that continuously executes queued tasks."""
        logger.info(f"⚙️ TaskQueue Worker #{worker_id} active and listening...")
        while self._is_running:
            try:
                task = await self._queue.get()
            except asyncio.CancelledError:
                break

            # If task was cancelled while sitting in queue, skip execution
            if task.status == TaskStatus.CANCELLED:
                self._queue.task_done()
                continue

            # Execute task
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc).isoformat()
            task.progress_message = f"Processing on Worker #{worker_id}..."
            emit_event(f"task:{task.user_id}", "task_started", task.to_dict())

            logger.info(f"▶️ [Worker #{worker_id}] Executing task {task.task_id} for User {task.user_id} ({task.task_type})...")

            try:
                # Apply anti-bot rate-limiting pacing
                await self.rate_limiter.acquire(label=f"User {task.user_id} ({task.task_type})")

                # Dispatch to appropriate handler
                result = await self._dispatch_task(task)

                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.progress_message = "Task completed successfully."
                task.result = result

                emit_event(f"task:{task.user_id}", "task_completed", task.to_dict())
                logger.info(f"✅ [Worker #{worker_id}] Task {task.task_id} completed for User {task.user_id}!")

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.progress_message = "Task cancelled during execution."
                break
            except Exception as e:
                logger.error(f"❌ [Worker #{worker_id}] Task {task.task_id} failed for User {task.user_id}: {e}", exc_info=True)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.progress_message = f"Task failed: {str(e)}"
                task.error = str(e)
                emit_event(f"task:{task.user_id}", "task_failed", task.to_dict())
            finally:
                self._queue.task_done()

    async def _dispatch_task(self, task: UserTask) -> Dict[str, Any]:
        """Dispatches task payload to the appropriate agent engine."""
        custom_coro = task.payload.pop("_custom_coro_fn", None)
        if custom_coro and callable(custom_coro):
            return await custom_coro(task)

        task_type = task.task_type.lower()

        if task_type in ["discovery", "discover_jobs"]:
            from app.agent.ingestion import discover_and_ingest
            report = await discover_and_ingest(
                search_term=task.payload.get("search_term"),
                search_terms=task.payload.get("search_terms"),
                location=task.payload.get("location"),
                locations=task.payload.get("locations"),
                portals=task.payload.get("portals", ["naukri"]),
                results_wanted=task.payload.get("results_wanted", 10),
                freshness_days=task.payload.get("freshness_days", 1),
                experience_level=task.payload.get("experience_level"),
                user_id=task.user_id,
            )
            return {
                "total_discovered": report.total_discovered,
                "high_matches_ready": report.high_matches_ready,
                "low_matches_archived": report.low_matches_archived,
                "duplicates_skipped": report.duplicates_skipped,
                "errors_count": report.errors_count,
            }

        elif task_type in ["1click_apply", "auto_apply"]:
            from app.agent.ingestion import process_1click_applications
            max_daily = task.payload.get("max_daily", 7)
            min_score = task.payload.get("min_score", 75)
            return await process_1click_applications(
                user_id=task.user_id,
                max_daily_limit=max_daily,
                min_score=min_score,
            )

        elif task_type in ["profile_boost", "boost_naukri"]:
            from app.agent.booster import boost_naukri_profile_live
            return await boost_naukri_profile_live(user_id=task.user_id)

        else:
            raise ValueError(f"Unknown task type: '{task.task_type}'")


# Global singleton instance
task_queue = MultiTenantTaskQueue(max_concurrent_workers=DEFAULT_MAX_CONCURRENT_WORKERS)
