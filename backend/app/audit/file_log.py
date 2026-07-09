from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.privacy import sanitize
from app.schemas.phase_a import AuditEvent


class AuditTrail:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.events: list[AuditEvent] = []

    def add(self, event: str, status: str = "ok", **details: Any) -> None:
        self.events.append(
            AuditEvent(
                timestamp=datetime.now(UTC).isoformat(),
                event=event,
                status=status,
                details=sanitize(details),
            )
        )

    def write(self) -> None:
        self.output_path.write_text(
            "[\n"
            + ",\n".join(f"  {event.model_dump_json()}" for event in self.events)
            + "\n]\n",
            encoding="utf-8",
        )

