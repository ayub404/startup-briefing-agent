"""Startup briefing agent: fetch fresh launches -> drop repeats -> LLM analysis -> email."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from briefing import emailer, llm, sources
from briefing.prompt import SYSTEM_PROMPT, build_user_message
from briefing.state import SeenStore

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("briefing")


def llm_key_set() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=int(os.getenv("BRIEFING_DAYS", "7")), help="look-back window")
    p.add_argument("--max", type=int, default=int(os.getenv("BRIEFING_MAX", "8")), help="startups per briefing")
    p.add_argument("--to", default=os.getenv("BRIEFING_TO", ""), help="recipient(s), comma-separated")
    p.add_argument("--dry-run", action="store_true", help="write output/ files only; no email, no state update")
    p.add_argument("--state", type=Path, default=ROOT / "state" / "seen.json")
    p.add_argument("--out", type=Path, default=ROOT / "output")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    missing = [] if os.getenv("LLM_PROVIDER") else ([] if llm_key_set() else ["ANTHROPIC_API_KEY or OPENAI_API_KEY"])
    if not args.dry_run:
        missing += [k for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD") if not os.getenv(k)]
        missing += [] if args.to else ["BRIEFING_TO (or --to)"]
    if missing:
        log.error("Missing configuration: %s", ", ".join(missing))
        return 2

    store = SeenStore(args.state)
    fresh = [x for x in sources.fetch_all(args.days) if x.id not in store]
    log.info("%d new launches after removing already-featured ones", len(fresh))
    if not fresh:
        log.info("Nothing new; no briefing sent.")
        return 0

    today = date.today().isoformat()
    raw = llm.complete(SYSTEM_PROMPT, build_user_message([x.to_dict() for x in fresh], args.max, today))
    subject, body, featured = emailer.parse_briefing(raw)
    known = {x.id for x in fresh}
    featured = [i for i in featured if i in known] or sorted(known)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "briefing.md").write_text(f"Subject: {subject}\n\n{body}\n")
    (args.out / "briefing.html").write_text(emailer.to_html(body))
    log.info("Subject: %s", subject)
    log.info("Wrote %s", args.out / "briefing.md")

    if args.dry_run:
        return 0
    emailer.send(subject, body, args.to)
    log.info("Sent to %s", args.to)
    store.add(featured)
    store.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
