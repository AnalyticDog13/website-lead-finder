# LA Lead Finder — Design Spec
_Date: 2026-06-05_

## Overview

A local web app that finds small businesses in the Los Angeles area that have no website or a poor-quality website, so the operator can contact them to sell web design services. The tool scrapes Google Places and Yelp, scores website quality using rules + AI, streams results live into a dashboard, and exports confirmed leads to CSV.

---

## Target Business Categories

- Photographers
- Coffee shops
- Barber shops
- Freelancers
- Real estate agents
- Workout / yoga studios

More categories can be added to a config list at any time.

---

## Architecture

```
Browser Dashboard (vanilla JS + HTML)
        │  HTTP + Server-Sent Events (real-time stream)
FastAPI Backend (Python)
   /api/scrape   → kicks off background scrape job
   /api/leads    → query/filter stored leads
   /api/stream   → SSE endpoint, streams new leads live
   /api/export   → returns CSV download
        │
  ┌─────┴──────┬──────────────────┐
Google Places  Yelp Fusion     ScrapeGraphAI
    API            API         (OpenAI or Claude)
        │                       visits weak websites
        └──────────┬────────────┘
               SQLite DB (leads.db)
```

**Single command to run:**
```bash
python main.py
# opens http://localhost:8000
```

**File structure:**
```
website-lead-finder/
├── main.py           # FastAPI app + all routes
├── scraper.py        # Google, Yelp, ScrapeGraphAI logic
├── models.py         # Lead data model + SQLite
├── static/
│   └── index.html    # Entire dashboard (vanilla JS + CSS)
├── .env              # API keys (never committed)
└── requirements.txt
```

---

## API Keys Required

| Key | Source | Cost |
|---|---|---|
| OpenAI API key | platform.openai.com | ~$0.001/lead |
| Anthropic API key | console.anthropic.com | ~$0.001/lead |
| Google Places API | console.cloud.google.com | ~$0.017/request, $200 free/month |
| Yelp Fusion API | yelp.com/developers | Free, 500 req/day |

All stored in `.env`, never committed to git.

---

## Data Pipeline

For each scrape run (user picks category + limit):

### 1. Discover
- Query Google Places API: `"<category> in Los Angeles CA"` → up to N results
- Query Yelp Fusion API: same search
- Merge and deduplicate by business name + address

### 2. Quick Filter (no AI cost)
| Condition | Action |
|---|---|
| No website listed | Auto-lead (high priority) |
| No HTTPS | Flagged bad → Auto-lead |
| No mobile viewport meta tag | Flagged bad |
| Page load > 5 seconds | Flagged bad |
| 2+ flags | Auto-lead |
| 1 flag | Review queue |
| Passes all checks | Review queue (AI scores it, user decides) |
| AI scores ≥ 8 | Skipped (but still browsable) |

### 3. AI Scoring (ScrapeGraphAI + LLM)
ScrapeGraphAI visits the website and extracts:
- Quality score 1–10
- Reason for score (e.g. "no contact page, broken images, last updated 2011")
- Email address if found on the page

### 4. Contact Extraction
- Phone: from Google / Yelp listing (most reliable)
- Email: from website scrape if found, otherwise blank

### 5. Stream + Save
- Each processed lead streams to the dashboard via SSE immediately
- Saved to SQLite

---

## Lead Data Model

| Field | Type | Example |
|---|---|---|
| id | int | 1 |
| business_name | str | "Cuts by Marco" |
| category | str | "barber shop" |
| phone | str | "(310) 555-0192" |
| email | str | "marco@cutsbymarco.com" |
| website_url | str | "http://cutsbymarco.weebly.com" |
| has_website | bool | true |
| quality_score | int 1–10 | 3 |
| quality_notes | str | "No HTTPS, no mobile layout" |
| source | str | "Google" |
| address | str | "1234 Sunset Blvd, Los Angeles CA" |
| status | enum | "lead" / "review" / "skipped" |
| user_notes | str | "outdated photos, no pricing" |
| scraped_at | datetime | 2026-06-05T14:23:00 |

---

## Dashboard UI

Plain HTML, no styling framework. Browser defaults are fine. Function over form.

**Layout (top to bottom):**

```
LA Lead Finder

[Run Scrape]  Category: [Barbers ▼]  Limit: [____]
Progress: 47/100 — Scoring cutsbymarco.weebly.com...

Filter: Category [All ▼]  Status [All ▼]  [Export CSV]

Tabs: [Auto-leads (23)] [Review Queue (41)] [Skipped (6)]

---
Table with columns:
  Business | Category | Phone | Email | Website | Score | Notes | Status | Actions
---
Row: Cuts by Marco | Barber | (310)555-0192 | marco@... | cutsbymarco.weebly.com [open] | 3/10 – No HTTPS, no mobile | [text input] | [Lead] [Skip]
Row: Silver Lake Coffee | Coffee | (323)555-0847 | — | No website | — | [text input] | [Lead] [Skip]
```

**Interactions:**
- "Run Scrape" button kicks off the job; progress line updates live via SSE
- New rows appear in the table as each lead streams in
- "open" link next to website opens it in a new tab for manual review
- Lead / Skip buttons update status instantly
- Notes text input auto-saves on blur
- Export CSV downloads only rows with status = "lead"

---

## Error Handling

- Google/Yelp API failures: log error, skip that source, continue with the other
- Website unreachable: mark quality_score = null, note "site unreachable"
- ScrapeGraphAI timeout: fall back to rule-based score only
- Rate limits: exponential backoff with a max of 3 retries

---

## Out of Scope

- Social media scraping (Instagram, Facebook, LinkedIn prohibit it in ToS — unreliable to automate)
- Email sending / CRM integration (manual outreach from the CSV)
- Deployment beyond localhost
- User accounts / authentication
