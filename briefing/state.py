"""Remembers which launches were already featured so briefings never repeat."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

RETENTION_DAYS = 120


class SeenStore:
    def __init__(self, path: Path):
        self.path = path
        self.seen: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}

    def __contains__(self, launch_id: str) -> bool:
        return launch_id in self.seen

    def add(self, ids: list[str], today: date | None = None) -> None:
        stamp = (today or date.today()).isoformat()
        for launch_id in ids:
            self.seen.setdefault(launch_id, stamp)

    def save(self, today: date | None = None) -> None:
        cutoff = ((today or date.today()) - timedelta(days=RETENTION_DAYS)).isoformat()
        self.seen = {k: v for k, v in self.seen.items() if v >= cutoff}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.seen, indent=2, sort_keys=True) + "\n")
