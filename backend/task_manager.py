# backend/task_manager.py
import asyncio
import logging

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
MAX_CONCURRENT_TASKS = 10


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

    return asyncio.create_task(_guarded(), name=name)
