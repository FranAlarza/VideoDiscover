"""Server-Sent Events endpoint for download updates."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.events.broker import DownloadEvent, DownloadEventBroker

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def download_events(request: Request) -> StreamingResponse:
    broker: DownloadEventBroker = request.app.state.download_event_broker
    last_event_id = _last_event_id(request.headers.get("last-event-id"))
    subscription = await broker.subscribe(last_event_id)

    async def stream() -> AsyncIterator[str]:
        try:
            if subscription.requires_snapshot:
                snapshot = await request.app.state.download_task_service.list()
                yield _format_sse(
                    event_id=None,
                    name="downloads.snapshot",
                    data=snapshot.model_dump(mode="json"),
                )
            for event in subscription.replay:
                yield format_download_event(event)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(subscription.queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield format_download_event(event)
        finally:
            await broker.unsubscribe(subscription)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def format_download_event(event: DownloadEvent) -> str:
    data = {"occurred_at": event.occurred_at.isoformat(), "task": event.data}
    return _format_sse(event_id=event.id, name=event.name, data=data)


def _format_sse(*, event_id: int | None, name: str, data: dict) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {name}")
    lines.append("data: " + json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + "\n\n"


def _last_event_id(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        return None
    return value if value >= 0 else None
