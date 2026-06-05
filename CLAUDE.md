# LA Lead Finder

Local web app that finds LA small businesses with no or poor websites and exports them as leads for web design outreach.

## What This Does

- Searches Google Places + Yelp for businesses in Los Angeles by category
- Runs rule-based quality checks on their websites (HTTPS, mobile viewport, load speed)
- Uses ScrapeGraphAI + OpenAI to score website quality 1–10 and extract contact emails
- Streams results live into a browser dashboard via Server-Sent Events
- Lets you manually review sites, mark as Lead or Skip, add notes
- Exports confirmed leads to CSV

## Running the App

```bash
python main.py
# opens at http://localhost:8000
```

## Running Tests

```bash
pytest tests/ -v
```

## Required API Keys

All keys go in `.env` (copy from `.env.example`):

| Variable | Where to get it |
|---|---|
| `OPENAI_API_KEY` | platform.openai.com |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `GOOGLE_PLACES_API_KEY` | console.cloud.google.com → Places API |
| `YELP_API_KEY` | yelp.com/developers → Fusion API |

## File Map

| File | Purpose |
|---|---|
| `main.py` | FastAPI app, all routes, SSE endpoint |
| `scraper.py` | Google/Yelp clients, quality checks, AI scoring, pipeline |
| `models.py` | Lead dataclass, SQLite schema, DB read/write |
| `static/index.html` | Dashboard — plain HTML table, vanilla JS |
| `leads.db` | SQLite database (created on first run, gitignored) |

## Business Categories

Defined in `scraper.py` → `CATEGORIES` list:
- photographers
- coffee shops
- barber shops
- freelancers
- real estate agents
- workout yoga studios

Add more by appending to that list.

## Lead Status Flow

- `review` — default, needs your decision
- `lead` — confirmed, included in CSV export
- `skipped` — dismissed (recoverable in the dashboard)

Businesses with no website or 2+ tech flags are auto-set to `lead`. Businesses with a good-looking site (AI score ≥ 8) are auto-set to `skipped`. Everything else lands in `review` for your manual eyeball.

## Design Docs

- Spec: `docs/superpowers/specs/2026-06-05-la-lead-finder-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-la-lead-finder.md`
