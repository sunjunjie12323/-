import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field

from app.config import settings


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: str
    status: TaskStatus = TaskStatus.PENDING
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        use_enum_values = False


class TaskQueue:
    def __init__(self, max_concurrent_tasks: int = 0):
        self.max_concurrent_tasks = max_concurrent_tasks or settings.MAX_CONCURRENT_TASKS
        self._tasks: Dict[str, Task] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running: bool = False
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        self._task_handlers: Dict[str, Callable[..., Coroutine]] = {}
        self._progress_callbacks: Dict[str, Callable] = {}

    def register_handler(self, task_type: str, handler: Callable[..., Coroutine]) -> None:
        self._task_handlers[task_type] = handler
        logger.info(f"Registered task handler for type: {task_type}")

    def register_progress_callback(self, task_id: str, callback: Callable) -> None:
        self._progress_callbacks[task_id] = callback

    async def submit(self, task_type: str, params: Dict[str, Any] = None) -> str:
        if task_type not in self._task_handlers:
            raise ValueError(f"No handler registered for task type: {task_type}")
        task = Task(
            type=task_type,
            params=params or {},
            status=TaskStatus.PENDING,
        )
        self._tasks[task.id] = task
        await self._queue.put(task.id)
        logger.info(f"Task submitted: {task.id} (type={task_type})")
        return task.id

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Task]:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[offset: offset + limit]

    async def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        logger.info(f"Task cancelled: {task_id}")
        return True

    def update_progress(self, task_id: str, progress: float) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.progress = max(0.0, min(100.0, progress))
            callback = self._progress_callbacks.get(task_id)
            if callback:
                try:
                    callback(task_id, progress)
                except Exception as exc:
                    logger.warning(f"Progress callback error for {task_id}: {exc}")

    async def start(self) -> None:
        if self._running:
            logger.warning("TaskQueue already running")
            return
        self._running = True
        for i in range(self.max_concurrent_tasks):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        logger.info(
            f"TaskQueue started with {self.max_concurrent_tasks} workers"
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._workers:
            await self._queue.put(None)
        for worker in self._workers:
            try:
                await asyncio.wait_for(worker, timeout=10.0)
            except asyncio.TimeoutError:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
        self._workers.clear()
        logger.info("TaskQueue stopped")

    async def _worker(self, worker_id: int) -> None:
        logger.debug(f"Worker {worker_id} started")
        while self._running:
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if task_id is None:
                break
            task = self._tasks.get(task_id)
            if task is None:
                continue
            if task.status == TaskStatus.CANCELLED:
                continue
            async with self._semaphore:
                if task.status == TaskStatus.CANCELLED:
                    continue
                await self._execute_task(task)
        logger.debug(f"Worker {worker_id} stopped")

    async def _execute_task(self, task: Task) -> None:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.progress = 0.0
        logger.info(f"Task started: {task.id} (type={task.type})")
        handler = self._task_handlers.get(task.type)
        if handler is None:
            task.status = TaskStatus.FAILED
            task.error = f"No handler for task type: {task.type}"
            task.completed_at = datetime.utcnow()
            logger.error(f"Task failed: {task.id} - {task.error}")
            return
        try:
            result = await handler(task)
            if task.status == TaskStatus.CANCELLED:
                return
            task.result = self._sanitize_result(result)
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            task.completed_at = datetime.utcnow()
            logger.info(f"Task completed: {task.id}")
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            logger.info(f"Task cancelled during execution: {task.id}")
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = datetime.utcnow()
            logger.error(f"Task failed: {task.id} - {exc}")
        finally:
            self._progress_callbacks.pop(task.id, None)

    def _sanitize_result(self, result: Any) -> Any:
        if result is None:
            return None
        try:
            import json
            json.dumps(result, default=str, ensure_ascii=False)
            return result
        except (TypeError, ValueError):
            if isinstance(result, dict):
                return {
                    k: self._sanitize_result(v)
                    for k, v in result.items()
                    if not k.startswith("_")
                }
            if isinstance(result, (list, tuple)):
                return [self._sanitize_result(item) for item in result]
            if hasattr(result, "model_dump"):
                return result.model_dump()
            if hasattr(result, "__dict__"):
                return {
                    k: self._sanitize_result(v)
                    for k, v in result.__dict__.items()
                    if not k.startswith("_")
                }
            return str(result)


task_queue = TaskQueue()
