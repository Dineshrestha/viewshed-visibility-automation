"""Checkpoint/resume state for long-running batch jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class RunStatus:
    """Persist site-level batch status as JSON."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = {"updated_utc": None, "sites": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.setdefault("sites", {})

    def is_complete(self, site_id: str) -> bool:
        return self.data["sites"].get(str(site_id), {}).get("status") == "Complete"

    def set(self, site_id: str, status: str, message: str = "", **metadata) -> None:
        record = {
            "status": status,
            "message": message,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
        }
        record.update(metadata)
        self.data["sites"][str(site_id)] = record
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_utc"] = datetime.now(timezone.utc).isoformat()
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
