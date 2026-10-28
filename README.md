# Startup Briefing Agent

An agent that turns fresh startup launches into an executive-level briefing email.

**Pipeline:** fetch launches → drop ones already featured → LLM analyst writes the briefing → email via Gmail.

| Source | How it's read |
| --- | --- |
| Y Combinator | "Launch HN" posts via the Hacker News Algolia API |
| Product Hunt | Public Atom feed + product page description |
| Devpost | Newest projects page + project write-up |
| UzCombinator | News page (Uzbek; translated by the LLM) |

Each startup gets: Source, Category, **What They Do**, **How They Do It**, **The Problem Solved**, followed by Key Takeaways & Emerging Trends. The analyst prompt lives in `briefing/prompt.py`.

Already-featured startups are recorded in `state/seen.json`, so you never get the same one twice.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in keys
set -a && source .env && set +a

python -m briefing.main --dry-run          # writes output/briefing.md + .html, no email
python -m briefing.main --to you@gmail.com # build and send
```

Options: `--days 7` (look-back window), `--max 8` (startups per email). Test the pipeline without an API key using `LLM_PROVIDER=mock`.

## Run on GitHub Actions

1. **Settings → Secrets and variables → Actions → Secrets:** add `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and either `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.
2. **Same page → Variables (or Secrets):** add `BRIEFING_TO` (e.g. `ayubxonayub54@gmail.com`), and optionally `LLM_MODEL`.
3. **Actions → Startup briefing → Run workflow.**
4. To get it daily, uncomment the `schedule` block in `.github/workflows/briefing.yml`.

`GMAIL_APP_PASSWORD` must be a 16-letter App Password from <https://myaccount.google.com/apppasswords> (requires 2-step verification), not your normal Gmail password.

## Add a source

Write a `fetch_xxx(since) -> list[Launch]` function in `briefing/sources.py` and register it in `FETCHERS`.
