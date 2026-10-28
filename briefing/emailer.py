"""Renders the Markdown briefing to HTML and sends it through Gmail SMTP."""

from __future__ import annotations

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown

STYLE = "font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:720px;margin:auto;line-height:1.55;color:#1a1a1a"


def parse_briefing(text: str) -> tuple[str, str, list[str]]:
    """Split LLM output into (subject, markdown body, featured ids)."""
    text = text.strip()
    text = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text)
    featured: list[str] = []
    m = re.search(r"<!--\s*featured:\s*(.*?)\s*-->", text, re.S)
    if m:
        featured = [i.strip() for i in m.group(1).split(",") if i.strip()]
        text = (text[: m.start()] + text[m.end() :]).strip()
    subject = "🚀 Fresh Startup Briefing"
    first, _, rest = text.partition("\n")
    s = re.match(r"\**Subject Line Suggestion:?\**:?\s*(.+)", first.strip())
    if s:
        subject = s.group(1).strip().strip("*").strip()
        text = rest.strip()
    return subject, text, featured


def to_html(body_md: str) -> str:
    return f'<html><body style="{STYLE}">{markdown.markdown(body_md)}</body></html>'


def send(subject: str, body_md: str, to: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"].strip()
    password = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "").strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.attach(MIMEText(body_md, "plain", "utf-8"))
    msg.attach(MIMEText(to_html(body_md), "html", "utf-8"))
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls()
        s.login(sender, password)
        s.send_message(msg, to_addrs=[a.strip() for a in to.split(",")])
