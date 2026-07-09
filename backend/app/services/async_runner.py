from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.services.single_file_review import run_review_stream

_runs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def start_review(input_path: Path, output_dir: Path, settings: Settings | None = None) -> str:
    if settings is None:
        settings = get_settings()
    run_id = uuid.uuid4().hex[:12]
    output_dir.mkdir(parents=True, exist_ok=True)

    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "stage": "starting",
            "label": "正在启动...",
            "progress": 0,
            "start_time": time.time(),
            "result_path": None,
            "error": None,
        }

    def _run():
        try:
            for event_json in _sync_collect(input_path, output_dir, settings):
                data = json.loads(event_json)
                stage = data.get("stage", "")
                label = data.get("label", "")
                with _lock:
                    r = _runs.get(run_id)
                    if r is None:
                        return
                    if stage == "done":
                        r["stage"] = "done"
                        r["label"] = "完成"
                        r["progress"] = 100
                        r["status"] = "done"
                        r["result_path"] = data.get("result_path")
                        r["filename"] = data.get("filename")
                    elif data.get("status") == "done":
                        r["stage"] = stage
                        r["label"] = label
                        stage_progress = {
                            "classify": 5, "ocr": 35, "split": 42, "llm": 75,
                            "consistency": 88, "excel": 98,
                        }
                        r["progress"] = stage_progress.get(stage, r["progress"])
                        if "errors" in data:
                            r["llm_errors"] = data["errors"]
                    elif data.get("status") == "active":
                        r["stage"] = stage
                        r["label"] = label
                    elif data.get("status") == "running":
                        r["stage"] = stage
                        r["label"] = label
                        if "progress" in data:
                            r["progress"] = data["progress"]
                        if "completed" in data and "total" in data:
                            r["llm_completed"] = data["completed"]
                            r["llm_total"] = data["total"]
        except Exception as exc:
            with _lock:
                r = _runs.get(run_id)
                if r:
                    r["status"] = "error"
                    r["error"] = str(exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return run_id


def get_run(run_id: str) -> dict[str, Any] | None:
    with _lock:
        return _runs.get(run_id)


def get_result_path(run_id: str) -> Path | None:
    with _lock:
        r = _runs.get(run_id)
        if r and r.get("result_path"):
            p = Path(r["result_path"])
            if p.exists():
                return p
    return None


def cleanup_run(run_id: str) -> None:
    with _lock:
        _runs.pop(run_id, None)


def _sync_collect(input_path: Path, output_dir: Path, settings: Settings):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        agen = run_review_stream(input_path, output_dir, settings).__aiter__()
        while True:
            try:
                event = loop.run_until_complete(agen.__anext__())
                yield event
            except StopAsyncIteration:
                break
    finally:
        loop.close()
