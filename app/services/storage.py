"""Artifact storage manager for traces, videos, screenshots, and auth states."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import aiofiles

from app.core.config import settings


class StorageService:
    """Manages on-disk artefact files for the platform."""

    # ── Trace files (.zip) ──────────────────────────────────────────────

    @staticmethod
    def trace_path(run_id: uuid.UUID, test_case_id: uuid.UUID) -> Path:
        """Return the canonical path for a trace archive."""
        dest = settings.traces_dir / str(run_id)
        dest.mkdir(parents=True, exist_ok=True)
        return dest / f"{test_case_id}.zip"

    @staticmethod
    def trace_dir_for_run(run_id: uuid.UUID) -> Path:
        dest = settings.traces_dir / str(run_id)
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    # ── Video files ─────────────────────────────────────────────────────

    @staticmethod
    def video_dir(run_id: uuid.UUID) -> Path:
        dest = settings.videos_dir / str(run_id)
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    # ── Screenshots ─────────────────────────────────────────────────────

    @staticmethod
    def screenshot_path(
        run_id: uuid.UUID,
        test_case_id: uuid.UUID,
        step_index: int,
        *,
        suffix: str = "",
    ) -> Path:
        dest = settings.screenshots_dir / str(run_id) / str(test_case_id)
        dest.mkdir(parents=True, exist_ok=True)
        name = f"step_{step_index}{suffix}.png"
        return dest / name

    @staticmethod
    def screenshot_file(
        run_id: uuid.UUID,
        test_case_id: uuid.UUID,
        step_index: int,
        *,
        kind: str = "step",
    ) -> Path:
        """Return an existing screenshot path without creating directories.

        kind: "step" | "failure" | "diff"
        """
        suffix = {"step": "", "failure": "_failure", "diff": "_diff"}.get(kind, "")
        return (
            settings.screenshots_dir
            / str(run_id)
            / str(test_case_id)
            / f"step_{step_index}{suffix}.png"
        )

    @staticmethod
    def baseline_screenshot_path(test_case_id: uuid.UUID, step_index: int) -> Path:
        dest = settings.screenshots_dir / "baselines" / str(test_case_id)
        dest.mkdir(parents=True, exist_ok=True)
        return dest / f"step_{step_index}.png"

    @staticmethod
    def diff_screenshot_path(
        run_id: uuid.UUID, test_case_id: uuid.UUID, step_index: int
    ) -> Path:
        dest = settings.screenshots_dir / str(run_id) / str(test_case_id)
        dest.mkdir(parents=True, exist_ok=True)
        return dest / f"step_{step_index}_diff.png"

    # ── Auth state ──────────────────────────────────────────────────────

    @staticmethod
    def auth_state_path(profile_id: uuid.UUID) -> Path:
        dest = settings.auth_states_dir
        dest.mkdir(parents=True, exist_ok=True)
        return dest / f"{profile_id}.json"

    @staticmethod
    async def save_auth_state(profile_id: uuid.UUID, state: dict) -> Path:
        path = StorageService.auth_state_path(profile_id)
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(state, indent=2))
        return path

    @staticmethod
    async def load_auth_state(profile_id: uuid.UUID) -> dict | None:
        path = StorageService.auth_state_path(profile_id)
        if not path.exists():
            return None
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        return json.loads(content)

    # ── Generic helpers ─────────────────────────────────────────────────

    @staticmethod
    async def save_bytes(path: Path, data: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return path

    @staticmethod
    async def read_bytes(path: Path) -> bytes | None:
        if not path.exists():
            return None
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    @staticmethod
    def delete_artefacts(run_id: uuid.UUID) -> None:
        """Remove all artefacts for a given run."""
        for base in (settings.traces_dir, settings.videos_dir, settings.screenshots_dir):
            target = base / str(run_id)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)

    @staticmethod
    async def save_json(path: Path, data: dict | list) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(data, indent=2, default=str))
        return path

    @staticmethod
    async def load_json(path: Path) -> dict | list | None:
        if not path.exists():
            return None
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        return json.loads(content)
