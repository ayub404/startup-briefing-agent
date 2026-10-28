from datetime import date

from briefing.emailer import parse_briefing, to_html
from briefing.state import SeenStore


def test_parse_briefing_extracts_subject_body_and_ids():
    raw = (
        "Subject Line Suggestion: 🚀 Fresh Startup Briefing: Agents\n\n---\n## ⚡ Executive Briefing\n\n"
        "### 1. Foo | Bar\n\n<!-- featured: hn:1, ph:foo -->"
    )
    subject, body, ids = parse_briefing(raw)
    assert subject == "🚀 Fresh Startup Briefing: Agents"
    assert body.startswith("---")
    assert "featured" not in body
    assert ids == ["hn:1", "ph:foo"]


def test_parse_briefing_handles_bold_subject_and_code_fence():
    subject, body, ids = parse_briefing("```markdown\n**Subject Line Suggestion:** Hello\n\nBody\n```")
    assert subject == "Hello"
    assert body == "Body"
    assert ids == []


def test_seen_store_roundtrip_and_pruning(tmp_path):
    path = tmp_path / "seen.json"
    store = SeenStore(path)
    store.add(["old"], today=date(2026, 1, 1))
    store.add(["new"], today=date(2026, 10, 1))
    store.save(today=date(2026, 10, 2))
    reloaded = SeenStore(path)
    assert "new" in reloaded
    assert "old" not in reloaded


def test_to_html_renders_markdown():
    assert "<h2>" in to_html("## Title")
