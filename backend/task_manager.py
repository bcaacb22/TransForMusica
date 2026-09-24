# backend/task_manager.py
import asyncio
import logging

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
MAX_CONCURRENT_TASKS = 10

# Strong references to in-flight tasks (asyncio only holds weak refs).
_background_tasks: set = set()


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    return _semaphore


async def create_bounded_task(coro, *, name: str = ""):
    """Wrap a coroutine in semaphore acquisition before executing."""
    sem = get_semaphore()

    async def _guarded():
        async with sem:
            logger.info(f"Task started: {name}")
            try:
                return await coro
            except Exception as e:
                logger.error(f"Task failed: {name} — {e}")
                raise
            finally:
                logger.info(f"Task slot released: {name}")

    task = asyncio.create_task(_guarded(), name=name)
    # asyncio keeps only a weak reference to tasks — without this strong ref a
    # fire-and-forget task can be garbage-collected mid-flight.
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
