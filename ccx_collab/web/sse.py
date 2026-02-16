"""Server-Sent Events (SSE) manager for real-time pipeline updates."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE connections for pipeline monitoring."""

    def __init__(self) -> None:
        self._queues: Dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, work_id: str) -> asyncio.Queue:
        """Subscribe to events for a pipeline run."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[work_id].append(queue)
        logger.debug(
            "SSE subscriber added for work_id=%s (total=%d)",
            work_id,
            len(self._queues[work_id]),
        )
        return queue

    def unsubscribe(self, work_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from events."""
        if work_id in self._queues:
            try:
                self._queues[work_id].remove(queue)
            except ValueError:
                pass
            if not self._queues[work_id]:
                del self._queues[work_id]

    async def publish(self, work_id: str, event: str, data: Dict[str, Any]) -> None:
        """Publish an event to all subscribers of a work_id."""
        if work_id not in self._queues:
            return
        message = {"event": event, "data": json.dumps(data)}
        for queue in self._queues[work_id]:
            await queue.put(message)
        logger.debug("SSE event published: work_id=%s, event=%s", work_id, event)

    async def publish_stage_update(
        self,
        work_id: str,
        stage: str,
        status: str,
        detail: Optional[str] = None,
    ) -> None:
        """Publish a stage update event."""
        data: Dict[str, Any] = {"stage": stage, "status": status}
        if detail:
            data["detail"] = detail
        await self.publish(work_id, "stage_update", data)

    async def publish_pipeline_complete(self, work_id: str, status: str) -> None:
        """Publish pipeline completion event."""
        await self.publish(work_id, "pipeline_complete", {"status": status})


# Global SSE manager instance
sse_manager = SSEManager()
