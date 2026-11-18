"""API routes for the recorder — start/stop sessions, inject assertions, WebSocket streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status

from app.schemas.test_schemas import (
    InjectAssertionRequest,
    RecorderStartRequest,
    RecorderStartResponse,
    RecorderStopResponse,
    RecordedStep,
    WSStepMessage,
)
from app.services.recorder import recorder_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recorder", tags=["recorder"])

# Track active WebSocket connections per session
_ws_connections: dict[str, list[WebSocket]] = {}


# ═══════════════════════════════════════════════════════════════════════
# REST endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.post("/start", response_model=RecorderStartResponse, status_code=status.HTTP_201_CREATED)
async def start_recording(req: RecorderStartRequest) -> RecorderStartResponse:
    """Launch a headed browser session and begin recording user actions.

    Returns a session ID and a WebSocket URL for real-time step streaming.
    """
    session = recorder_manager.create_session()

    async def on_step(step: RecordedStep) -> None:
        """Push each captured step to all connected WebSocket clients."""
        msg = WSStepMessage(session_id=session.session_id, step=step)
        payload = msg.model_dump_json()
        ws_list = _ws_connections.get(session.session_id, [])
        dead: list[WebSocket] = []
        for ws in ws_list:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for d in dead:
            ws_list.remove(d)

    # Launch browser in background (non-blocking)
    asyncio.create_task(
        session.start(
            url=req.url,
            browser_type=req.browser,
            device_config=req.device_config,
            headless=req.headless,
            on_step=on_step,
        )
    )

    return RecorderStartResponse(
        session_id=session.session_id,
        ws_url=f"/ws/recorder/{session.session_id}",
    )


@router.post("/stop/{session_id}", response_model=RecorderStopResponse)
async def stop_recording(session_id: str) -> RecorderStopResponse:
    """Stop a recording session, close the browser, and return all captured steps."""
    session = recorder_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    steps, duration_ms = await session.stop()
    recorder_manager.remove_session(session_id)

    # Close all WebSocket connections for this session
    ws_list = _ws_connections.pop(session_id, [])
    for ws in ws_list:
        try:
            await ws.close(code=1000, reason="Recording stopped")
        except Exception:
            pass

    return RecorderStopResponse(
        session_id=session_id,
        steps=steps,
        duration_ms=duration_ms,
    )


@router.post("/assert/{session_id}", status_code=status.HTTP_201_CREATED)
async def inject_assertion(session_id: str, req: InjectAssertionRequest) -> dict[str, str]:
    """Inject an assertion at the current point in the recording session."""
    session = recorder_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if not session.is_running:
        raise HTTPException(status_code=409, detail="Session is not currently recording")

    await session.add_assertion(req.assertion)
    return {"status": "assertion_added", "type": req.assertion.assertion_type.value}


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """List all active recording sessions."""
    return {
        "active_sessions": recorder_manager.active_sessions,
        "count": len(recorder_manager.active_sessions),
    }


# ═══════════════════════════════════════════════════════════════════════
# WebSocket endpoint for real-time step streaming
# ═══════════════════════════════════════════════════════════════════════


@router.websocket("/ws/recorder/{session_id}")
async def ws_recorder(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint that streams recorded steps in real time.

    Clients connect here after calling POST /recorder/start to receive
    each captured step as a JSON message.
    """
    session = recorder_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()

    if session_id not in _ws_connections:
        _ws_connections[session_id] = []
    _ws_connections[session_id].append(websocket)

    logger.info("WebSocket connected for recorder session %s", session_id)

    try:
        # Send any already-captured steps
        for step in session.steps:
            msg = WSStepMessage(session_id=session_id, step=step)
            await websocket.send_text(msg.model_dump_json())

        # Keep the connection alive until the client disconnects
        while True:
            # Wait for client messages (e.g., keep-alive pings)
            data = await websocket.receive_text()
            # Clients can send assertion commands via WebSocket too
            try:
                payload = json.loads(data)
                if payload.get("type") == "assertion":
                    from app.schemas.test_schemas import AssertionStep

                    assertion = AssertionStep(**payload.get("assertion", {}))
                    await session.add_assertion(assertion)
                    await websocket.send_text(
                        json.dumps({"type": "assertion_added", "assertion_type": assertion.assertion_type.value})
                    )
            except (json.JSONDecodeError, Exception) as exc:
                await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for recorder session %s", session_id)
    finally:
        ws_list = _ws_connections.get(session_id, [])
        if websocket in ws_list:
            ws_list.remove(websocket)
