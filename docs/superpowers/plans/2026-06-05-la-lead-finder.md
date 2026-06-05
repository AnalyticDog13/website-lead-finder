# LA Lead Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app that finds LA small businesses with no or poor websites and exports confirmed leads to CSV for web design outreach.

**Architecture:** FastAPI backend serves a plain HTML dashboard. A background async task scrapes Google Places and Yelp APIs, runs rule-based quality checks then AI scoring via ScrapeGraphAI, and streams each processed lead to the browser via Server-Sent Events. All leads persist in SQLite.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, SQLite (stdlib), googlemaps, requests, BeautifulSoup4, ScrapeGraphAI, python-dotenv, pytest, unittest.mock

---

## File Map

```
website-lead-finder/
├── main.py             # FastAPI app, all routes, SSE endpoint, startup
├── scraper.py          # Google Places client, Yelp client, quality checks, AI scoring, pipeline
├── models.py           # Lead dataclass, SQLite schema, DB operations
├── static/
│   └── index.html      # Entire dashboard — plain HTML table, vanilla JS
├── tests/
│   ├── test_models.py
│   ├── test_scraper.py
│   └── test_main.py
├── .env                # API keys (gitignored)
├── .env.example        # Template committed to git
├── .gitignore
└── requirements.txt
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.0
python-dotenv==1.0.0
googlemaps==4.10.0
requests==2.32.0
beautifulsoup4==4.12.0
scrapegraphai==1.13.0
playwright==1.44.0
aiofiles==23.2.0
pytest==8.2.0
httpx==0.27.0
```

- [ ] **Step 2: Create .env.example**

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_PLACES_API_KEY=AIza...
YELP_API_KEY=...
```

- [ ] **Step 3: Create .gitignore**

```
.env
leads.db
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Install dependencies**

Run:
```bash
pip install -r requirements.txt
playwright install
```

Expected: all packages install without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example .gitignore
git commit -m "feat: project scaffolding"
```

---

### Task 2: Lead Data Model and SQLite Operations

**Files:**
- Create: `models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_models.py`:

```python
import os
import pytest
from models import Lead, init_db, insert_lead, get_leads, update_lead_status

DB_PATH = "test_leads.db"

@pytest.fixture(autouse=True)
def clean_db():
    init_db(DB_PATH)
    yield
    os.remove(DB_PATH)

def make_lead(**kwargs):
    defaults = dict(
        business_name="Test Biz",
        category="barber shop",
        phone="(310) 555-0001",
        email="test@test.com",
        website_url="https://example.com",
        has_website=True,
        quality_score=3,
        quality_notes="No HTTPS",
        source="Google",
        address="123 Main St, Los Angeles CA",
        status="review",
        user_notes="",
        scraped_at="2026-06-05T12:00:00",
    )
    defaults.update(kwargs)
    return Lead(**defaults)

def test_insert_lead_returns_id():
    lead = make_lead()
    lead_id = insert_lead(lead, DB_PATH)
    assert isinstance(lead_id, int)
    assert lead_id > 0

def test_get_leads_returns_inserted():
    insert_lead(make_lead(business_name="Biz A", status="lead"), DB_PATH)
    insert_lead(make_lead(business_name="Biz B", status="review"), DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert len(leads) == 2

def test_get_leads_filters_by_status():
    insert_lead(make_lead(status="lead"), DB_PATH)
    insert_lead(make_lead(status="review"), DB_PATH)
    leads = get_leads(status="lead", db_path=DB_PATH)
    assert len(leads) == 1
    assert leads[0]["status"] == "lead"

def test_get_leads_filters_by_category():
    insert_lead(make_lead(category="barber shop"), DB_PATH)
    insert_lead(make_lead(category="coffee shop"), DB_PATH)
    leads = get_leads(category="barber shop", db_path=DB_PATH)
    assert len(leads) == 1
    assert leads[0]["category"] == "barber shop"

def test_update_lead_status():
    lead_id = insert_lead(make_lead(status="review"), DB_PATH)
    update_lead_status(lead_id, "lead", db_path=DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert leads[0]["status"] == "lead"

def test_update_lead_status_with_notes():
    lead_id = insert_lead(make_lead(), DB_PATH)
    update_lead_status(lead_id, "lead", user_notes="great prospect", db_path=DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert leads[0]["user_notes"] == "great prospect"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Implement models.py**

```python
import sqlite3
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Lead:
    business_name: str
    category: str
    phone: str
    email: str
    website_url: str
    has_website: bool
    quality_score: Optional[int]
    quality_notes: str
    source: str
    address: str
    status: str
    user_notes: str
    scraped_at: str
    id: Optional[int] = None

def init_db(db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            category TEXT,
            phone TEXT,
            email TEXT,
            website_url TEXT,
            has_website INTEGER,
            quality_score INTEGER,
            quality_notes TEXT,
            source TEXT,
            address TEXT,
            status TEXT DEFAULT 'review',
            user_notes TEXT DEFAULT '',
            scraped_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_lead(lead: Lead, db_path: str = "leads.db") -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        INSERT INTO leads (business_name, category, phone, email, website_url,
                          has_website, quality_score, quality_notes, source,
                          address, status, user_notes, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead.business_name, lead.category, lead.phone, lead.email,
        lead.website_url, int(lead.has_website), lead.quality_score,
        lead.quality_notes, lead.source, lead.address, lead.status,
        lead.user_notes, lead.scraped_at,
    ))
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()
    return lead_id

def get_leads(db_path: str = "leads.db", category: str = None, status: str = None) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM leads WHERE 1=1"
    params = []
    if category and category != "all":
        query += " AND category = ?"
        params.append(category)
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY scraped_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_lead_status(lead_id: int, status: str, user_notes: str = None, db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
    if user_notes is not None:
        conn.execute("UPDATE leads SET status = ?, user_notes = ? WHERE id = ?",
                     (status, user_notes, lead_id))
    else:
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: lead data model and SQLite operations"
```

---

### Task 3: Website Quality Rules Checker

**Files:**
- Create: `scraper.py` (partial — quality check only)
- Create: `tests/test_scraper.py` (partial)

- [ ] **Step 1: Write failing tests**

Create `tests/test_scraper.py`:

```python
from unittest.mock import patch, MagicMock
from scraper import check_website_quality

def test_flags_missing_https():
    result = check_website_quality("http://example.com")
    assert "No HTTPS" in result["flags"]

def test_flags_slow_load():
    mock_response = MagicMock()
    mock_response.text = "<html><head><meta name='viewport' content='width=device-width'></head></html>"

    with patch("scraper.requests.get", return_value=mock_response), \
         patch("scraper.time.time", side_effect=[0, 6]):  # 6 second load
        result = check_website_quality("https://slow-site.com")
    assert "Slow load" in " ".join(result["flags"])

def test_flags_missing_viewport():
    mock_response = MagicMock()
    mock_response.text = "<html><head></head><body></body></html>"

    with patch("scraper.requests.get", return_value=mock_response), \
         patch("scraper.time.time", side_effect=[0, 1]):
        result = check_website_quality("https://example.com")
    assert "No mobile viewport" in result["flags"]

def test_no_flags_for_good_site():
    mock_response = MagicMock()
    mock_response.text = "<html><head><meta name='viewport' content='width=device-width'></head></html>"

    with patch("scraper.requests.get", return_value=mock_response), \
         patch("scraper.time.time", side_effect=[0, 1]):
        result = check_website_quality("https://example.com")
    assert result["flag_count"] == 0

def test_flags_unreachable_site():
    with patch("scraper.requests.get", side_effect=Exception("Connection refused")):
        result = check_website_quality("https://dead-site.com")
    assert any("unreachable" in f.lower() for f in result["flags"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: Implement scraper.py with check_website_quality**

```python
import os
import time
import requests
from bs4 import BeautifulSoup

CATEGORIES = [
    "photographers",
    "coffee shops",
    "barber shops",
    "freelancers",
    "real estate agents",
    "workout yoga studios",
]

def check_website_quality(url: str) -> dict:
    flags = []

    if not url.startswith("https://"):
        flags.append("No HTTPS")

    try:
        start = time.time()
        response = requests.get(
            url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        load_time = time.time() - start

        if load_time > 5:
            flags.append(f"Slow load ({load_time:.1f}s)")

        soup = BeautifulSoup(response.text, "html.parser")
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            flags.append("No mobile viewport")

    except Exception as e:
        flags.append(f"Site unreachable: {str(e)[:50]}")

    return {"flags": flags, "flag_count": len(flags)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: rules-based website quality checker"
```

---

### Task 4: Google Places API Client

**Files:**
- Modify: `scraper.py` (add `search_google_places`)
- Modify: `tests/test_scraper.py` (add Google tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
from scraper import search_google_places

def test_search_google_places_returns_list():
    mock_client = MagicMock()
    mock_client.places.return_value = {
        "results": [{"place_id": "abc123", "name": "Test Barber"}]
    }
    mock_client.place.return_value = {
        "result": {
            "name": "Test Barber",
            "formatted_phone_number": "(310) 555-0001",
            "website": "http://testbarber.com",
            "formatted_address": "123 Main St, Los Angeles CA",
        }
    }

    with patch("scraper.googlemaps.Client", return_value=mock_client), \
         patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake-key"}):
        results = search_google_places("barber shops", limit=1)

    assert len(results) == 1
    assert results[0]["name"] == "Test Barber"
    assert results[0]["phone"] == "(310) 555-0001"
    assert results[0]["website"] == "http://testbarber.com"
    assert results[0]["source"] == "Google"

def test_search_google_places_handles_missing_fields():
    mock_client = MagicMock()
    mock_client.places.return_value = {
        "results": [{"place_id": "abc123"}]
    }
    mock_client.place.return_value = {"result": {}}

    with patch("scraper.googlemaps.Client", return_value=mock_client), \
         patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake-key"}):
        results = search_google_places("barber shops", limit=1)

    assert results[0]["phone"] == ""
    assert results[0]["website"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_search_google_places_returns_list -v
```

Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Add search_google_places to scraper.py**

Add at the top of scraper.py (after existing imports):

```python
import googlemaps
```

Add this function after `check_website_quality`:

```python
def search_google_places(category: str, limit: int) -> list:
    gmaps = googlemaps.Client(key=os.getenv("GOOGLE_PLACES_API_KEY"))
    results = []
    query = f"{category} in Los Angeles CA"
    response = gmaps.places(query=query)
    results.extend(response.get("results", []))

    while len(results) < limit and "next_page_token" in response:
        time.sleep(2)  # Google requires 2s delay between page token requests
        response = gmaps.places(query=query, page_token=response["next_page_token"])
        results.extend(response.get("results", []))

    businesses = []
    for place in results[:limit]:
        details = gmaps.place(
            place["place_id"],
            fields=["name", "formatted_phone_number", "website", "formatted_address"],
        )["result"]
        businesses.append({
            "name": details.get("name", ""),
            "phone": details.get("formatted_phone_number", ""),
            "website": details.get("website", ""),
            "address": details.get("formatted_address", ""),
            "source": "Google",
        })

    return businesses
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py::test_search_google_places_returns_list tests/test_scraper.py::test_search_google_places_handles_missing_fields -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: Google Places API client"
```

---

### Task 5: Yelp Fusion API Client

**Files:**
- Modify: `scraper.py` (add `search_yelp`)
- Modify: `tests/test_scraper.py` (add Yelp tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
from scraper import search_yelp

def test_search_yelp_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "businesses": [
            {
                "name": "Silver Lake Coffee",
                "phone": "+13235550001",
                "location": {"display_address": ["123 Sunset Blvd", "Los Angeles, CA 90026"]},
                "url": "https://yelp.com/biz/silver-lake-coffee",
            }
        ]
    }

    with patch("scraper.requests.get", return_value=mock_response), \
         patch.dict("os.environ", {"YELP_API_KEY": "fake-key"}):
        results = search_yelp("coffee shops", limit=1)

    assert len(results) == 1
    assert results[0]["name"] == "Silver Lake Coffee"
    assert results[0]["phone"] == "+13235550001"
    assert results[0]["source"] == "Yelp"

def test_search_yelp_handles_empty_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {"businesses": []}

    with patch("scraper.requests.get", return_value=mock_response), \
         patch.dict("os.environ", {"YELP_API_KEY": "fake-key"}):
        results = search_yelp("coffee shops", limit=10)

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_search_yelp_returns_list -v
```

Expected: `ImportError`

- [ ] **Step 3: Add search_yelp to scraper.py**

Add after `search_google_places`:

```python
def search_yelp(category: str, limit: int) -> list:
    headers = {"Authorization": f"Bearer {os.getenv('YELP_API_KEY')}"}
    params = {
        "term": category,
        "location": "Los Angeles, CA",
        "limit": min(limit, 50),
    }
    response = requests.get(
        "https://api.yelp.com/v3/businesses/search",
        headers=headers,
        params=params,
    )
    businesses = []
    for biz in response.json().get("businesses", []):
        businesses.append({
            "name": biz.get("name", ""),
            "phone": biz.get("phone", ""),
            "website": "",
            "address": ", ".join(biz.get("location", {}).get("display_address", [])),
            "source": "Yelp",
        })
    return businesses
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py::test_search_yelp_returns_list tests/test_scraper.py::test_search_yelp_handles_empty_response -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: Yelp Fusion API client"
```

---

### Task 6: AI Scoring with ScrapeGraphAI

**Files:**
- Modify: `scraper.py` (add `score_website_with_ai`)
- Modify: `tests/test_scraper.py` (add AI scoring tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
from scraper import score_website_with_ai

def test_score_website_with_ai_returns_score():
    mock_graph = MagicMock()
    mock_graph.run.return_value = {
        "score": 3,
        "notes": "Outdated design, no contact page",
        "email": "owner@example.com",
    }

    with patch("scraper.SmartScraperGraph", return_value=mock_graph), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
        result = score_website_with_ai("https://example.com")

    assert result["score"] == 3
    assert result["email"] == "owner@example.com"
    assert "Outdated" in result["notes"]

def test_score_website_with_ai_handles_failure():
    mock_graph = MagicMock()
    mock_graph.run.side_effect = Exception("LLM error")

    with patch("scraper.SmartScraperGraph", return_value=mock_graph), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
        result = score_website_with_ai("https://example.com")

    assert result["score"] is None
    assert result["email"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_score_website_with_ai_returns_score -v
```

Expected: `ImportError`

- [ ] **Step 3: Add score_website_with_ai to scraper.py**

Add at the top of scraper.py (after existing imports):

```python
from scrapegraphai.graphs import SmartScraperGraph
```

Add this function after `search_yelp`:

```python
def score_website_with_ai(url: str) -> dict:
    config = {
        "llm": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": "openai/gpt-4o-mini",
        },
        "verbose": False,
    }

    graph = SmartScraperGraph(
        prompt=(
            "Analyze this business website and return a JSON object with exactly these keys: "
            "score (integer 1-10, where 1=terrible and 10=professional/modern), "
            "notes (one sentence explaining the score — mention specific problems like outdated design, "
            "missing contact info, broken images, no portfolio), "
            "email (any contact email found on the page, or empty string if none). "
            "Return ONLY valid JSON, no other text."
        ),
        source=url,
        config=config,
    )

    try:
        result = graph.run()
        if isinstance(result, dict):
            return {
                "score": int(result.get("score", 5)),
                "notes": result.get("notes", ""),
                "email": result.get("email", ""),
            }
    except Exception:
        pass

    return {"score": None, "notes": "AI scoring failed", "email": ""}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py::test_score_website_with_ai_returns_score tests/test_scraper.py::test_score_website_with_ai_handles_failure -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: AI website scoring with ScrapeGraphAI"
```

---

### Task 7: Scrape Pipeline Orchestration

**Files:**
- Modify: `scraper.py` (add `deduplicate`, `process_business`, `run_scrape_pipeline`)
- Modify: `tests/test_scraper.py` (add pipeline tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_scraper.py`:

```python
import asyncio
from scraper import deduplicate, process_business, run_scrape_pipeline

def test_deduplicate_removes_same_name():
    businesses = [
        {"name": "Test Barber", "phone": "111", "website": "", "address": "123 Main", "source": "Google"},
        {"name": "test barber", "phone": "222", "website": "", "address": "123 Main", "source": "Yelp"},
        {"name": "Other Shop", "phone": "333", "website": "", "address": "456 Oak", "source": "Yelp"},
    ]
    result = deduplicate(businesses)
    assert len(result) == 2
    assert result[0]["name"] == "Test Barber"

def test_process_business_no_website_is_auto_lead():
    biz = {"name": "No Web Biz", "phone": "111", "website": "", "address": "LA", "source": "Google"}

    with patch("scraper.check_website_quality") as mock_check, \
         patch("scraper.score_website_with_ai") as mock_score, \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "lead"
    assert result.has_website is False
    mock_check.assert_not_called()
    mock_score.assert_not_called()

def test_process_business_two_flags_is_auto_lead():
    biz = {"name": "Bad Site", "phone": "111", "website": "http://bad.com", "address": "LA", "source": "Google"}

    with patch("scraper.check_website_quality", return_value={"flags": ["No HTTPS", "No mobile viewport"], "flag_count": 2}), \
         patch("scraper.score_website_with_ai") as mock_score, \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "lead"
    mock_score.assert_not_called()

def test_process_business_high_ai_score_is_skipped():
    biz = {"name": "Good Site", "phone": "111", "website": "https://good.com", "address": "LA", "source": "Google"}

    with patch("scraper.check_website_quality", return_value={"flags": [], "flag_count": 0}), \
         patch("scraper.score_website_with_ai", return_value={"score": 9, "notes": "Great site", "email": ""}), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "skipped"

def test_run_scrape_pipeline_streams_leads():
    biz = {"name": "Test", "phone": "111", "website": "", "address": "LA", "source": "Google"}

    with patch("scraper.search_google_places", return_value=[biz]), \
         patch("scraper.search_yelp", return_value=[]), \
         patch("scraper.process_business") as mock_process, \
         patch("scraper.insert_lead", return_value=1):

        from models import Lead
        from datetime import datetime
        mock_lead = Lead(
            business_name="Test", category="barber shop", phone="111",
            email="", website_url="", has_website=False, quality_score=None,
            quality_notes="No website", source="Google", address="LA",
            status="lead", user_notes="", scraped_at=datetime.utcnow().isoformat(), id=1,
        )
        mock_process.return_value = mock_lead

        queue = asyncio.Queue()
        asyncio.run(run_scrape_pipeline("barber shop", 1, queue))

        items = []
        while not queue.empty():
            items.append(queue.get_nowait())

    types = [i["type"] for i in items]
    assert "lead" in types
    assert "done" in types
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_deduplicate_removes_same_name -v
```

Expected: `ImportError`

- [ ] **Step 3: Add pipeline functions to scraper.py**

Add at top of scraper.py:

```python
import asyncio
from dataclasses import asdict
from datetime import datetime
from models import Lead, insert_lead
```

Add these functions after `score_website_with_ai`:

```python
def deduplicate(businesses: list) -> list:
    seen = set()
    unique = []
    for biz in businesses:
        key = biz["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(biz)
    return unique


def process_business(biz: dict, category: str, db_path: str = "leads.db") -> Lead:
    website = biz.get("website", "")
    has_website = bool(website)
    quality_score = None
    quality_notes = ""
    email = ""
    status = "review"

    if not has_website:
        status = "lead"
        quality_notes = "No website"
    else:
        quality = check_website_quality(website)
        flags = quality["flags"]
        flag_count = quality["flag_count"]
        quality_notes = " · ".join(flags) if flags else "Passed basic checks"

        if flag_count >= 2:
            status = "lead"
        else:
            ai = score_website_with_ai(website)
            quality_score = ai["score"]
            email = ai["email"]
            if ai["notes"]:
                quality_notes = f"{quality_notes} | AI: {ai['notes']}" if quality_notes else ai["notes"]

            if quality_score is not None and quality_score >= 8:
                status = "skipped"

    lead = Lead(
        business_name=biz["name"],
        category=category,
        phone=biz.get("phone", ""),
        email=email,
        website_url=website,
        has_website=has_website,
        quality_score=quality_score,
        quality_notes=quality_notes,
        source=biz.get("source", ""),
        address=biz.get("address", ""),
        status=status,
        user_notes="",
        scraped_at=datetime.utcnow().isoformat(),
    )
    lead.id = insert_lead(lead, db_path)
    return lead


async def run_scrape_pipeline(category: str, limit: int, queue: asyncio.Queue, db_path: str = "leads.db"):
    google_results = await asyncio.to_thread(search_google_places, category, limit)
    yelp_results = await asyncio.to_thread(search_yelp, category, limit)

    businesses = deduplicate(google_results + yelp_results)[:limit]

    for i, biz in enumerate(businesses):
        await queue.put({
            "type": "progress",
            "current": i + 1,
            "total": len(businesses),
            "message": f"Processing {biz['name']}...",
        })
        lead = await asyncio.to_thread(process_business, biz, category, db_path)
        await queue.put({"type": "lead", **asdict(lead)})

    await queue.put({"type": "done"})
```

- [ ] **Step 4: Run all scraper tests**

```bash
pytest tests/test_scraper.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: scrape pipeline orchestration"
```

---

### Task 8: FastAPI Backend

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_main.py`:

```python
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GOOGLE_PLACES_API_KEY", "fake")
os.environ.setdefault("YELP_API_KEY", "fake")
os.environ.setdefault("OPENAI_API_KEY", "fake")

from main import app
from models import init_db, insert_lead, Lead
from datetime import datetime

DB_PATH = "test_main.db"

@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.setenv("DB_PATH", DB_PATH)
    init_db(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

client = TestClient(app)

def make_lead(**kwargs):
    defaults = dict(
        business_name="Test Biz", category="barber shop", phone="310-555-0001",
        email="", website_url="", has_website=False, quality_score=None,
        quality_notes="No website", source="Google", address="LA",
        status="review", user_notes="", scraped_at=datetime.utcnow().isoformat(),
    )
    defaults.update(kwargs)
    return Lead(**defaults)

def test_get_leads_empty():
    response = client.get("/api/leads", params={"db_path": DB_PATH})
    assert response.status_code == 200
    assert response.json() == []

def test_get_leads_returns_data():
    insert_lead(make_lead(business_name="Biz A"), DB_PATH)
    response = client.get("/api/leads", params={"db_path": DB_PATH})
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_patch_lead_status():
    lead_id = insert_lead(make_lead(status="review"), DB_PATH)
    response = client.patch(f"/api/leads/{lead_id}", params={"status": "lead", "db_path": DB_PATH})
    assert response.status_code == 200
    leads = client.get("/api/leads", params={"db_path": DB_PATH}).json()
    assert leads[0]["status"] == "lead"

def test_export_csv_returns_file():
    insert_lead(make_lead(status="lead"), DB_PATH)
    response = client.get("/api/export", params={"db_path": DB_PATH})
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Test Biz" in response.text

def test_index_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create main.py**

```python
import asyncio
import csv
import io
import json
import os
from dataclasses import asdict

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from models import get_leads, init_db, update_lead_status
from scraper import CATEGORIES, run_scrape_pipeline

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

_scrape_queue: asyncio.Queue = asyncio.Queue()
_scrape_task = None


@app.on_event("startup")
async def startup():
    init_db(os.getenv("DB_PATH", "leads.db"))


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/categories")
async def categories():
    return CATEGORIES


@app.post("/api/scrape")
async def start_scrape(category: str, limit: int, db_path: str = "leads.db"):
    global _scrape_task, _scrape_queue
    if _scrape_task and not _scrape_task.done():
        return {"error": "Scrape already running"}
    _scrape_queue = asyncio.Queue()
    _scrape_task = asyncio.create_task(
        run_scrape_pipeline(category, limit, _scrape_queue, db_path)
    )
    return {"status": "started"}


@app.get("/api/stream")
async def stream():
    async def event_generator():
        while True:
            item = await _scrape_queue.get()
            if item["type"] == "done":
                yield "event: done\ndata: {}\n\n"
                break
            elif item["type"] == "progress":
                yield f"event: progress\ndata: {json.dumps(item)}\n\n"
            else:
                yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/leads")
async def get_leads_endpoint(category: str = "all", status: str = "all", db_path: str = "leads.db"):
    return get_leads(db_path=db_path, category=category, status=status)


@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: int, status: str, user_notes: str = None, db_path: str = "leads.db"):
    update_lead_status(lead_id, status, user_notes, db_path)
    return {"ok": True}


@app.get("/api/export")
async def export_csv(db_path: str = "leads.db"):
    leads = get_leads(status="lead", db_path=db_path)
    output = io.StringIO()
    fields = ["id", "business_name", "category", "phone", "email",
              "website_url", "has_website", "quality_score", "quality_notes",
              "source", "address", "user_notes", "scraped_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(leads)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: FastAPI backend with SSE streaming"
```

---

### Task 9: Dashboard HTML

**Files:**
- Create: `static/index.html`

No automated tests — verify manually by running the app and clicking through it.

- [ ] **Step 1: Create static/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LA Lead Finder</title>
  <style>
    body { font-family: sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 14px; }
    th { background: #f0f0f0; }
    .tabs { margin: 16px 0 4px; }
    .tabs button { margin-right: 4px; padding: 6px 14px; cursor: pointer; }
    .tabs button.active { font-weight: bold; background: #ddd; }
    #progress-bar { display: none; margin: 8px 0; }
    #status-msg { font-size: 13px; color: #555; }
    input[type=text] { width: 100%; box-sizing: border-box; }
    a { color: #0066cc; }
  </style>
</head>
<body>
  <h2>LA Lead Finder</h2>

  <div>
    <strong>Run Scrape:</strong>
    <select id="scrape-category"></select>
    <input id="scrape-limit" type="number" value="50" min="1" max="500" style="width:70px">
    <button onclick="startScrape()">▶ Run Scrape</button>
    <button onclick="exportCsv()">⬇ Export CSV (leads only)</button>
  </div>

  <div id="progress-bar">
    <progress id="progress" value="0" max="100"></progress>
    <span id="status-msg"></span>
  </div>

  <hr>

  <div>
    <strong>Filter:</strong>
    Category: <select id="filter-category" onchange="loadLeads()"><option value="all">All</option></select>
    &nbsp; Status: <select id="filter-status" onchange="loadLeads()">
      <option value="all">All</option>
      <option value="lead">Lead</option>
      <option value="review">Review Queue</option>
      <option value="skipped">Skipped</option>
    </select>
  </div>

  <div class="tabs">
    <button onclick="setTab('lead')" id="tab-lead">Auto-leads (<span id="count-lead">0</span>)</button>
    <button onclick="setTab('review')" id="tab-review">Review Queue (<span id="count-review">0</span>)</button>
    <button onclick="setTab('skipped')" id="tab-skipped">Skipped (<span id="count-skipped">0</span>)</button>
    <button onclick="setTab('all')" id="tab-all" class="active">All (<span id="count-all">0</span>)</button>
  </div>

  <table id="leads-table">
    <thead>
      <tr>
        <th>Business</th><th>Category</th><th>Phone</th><th>Email</th>
        <th>Website</th><th>Score</th><th>Notes (AI)</th><th>Your Notes</th><th>Status</th><th>Actions</th>
      </tr>
    </thead>
    <tbody id="leads-body"></tbody>
  </table>

  <script>
    let currentTab = 'all';
    let allLeads = [];
    let eventSource = null;

    async function init() {
      const cats = await fetch('/api/categories').then(r => r.json());
      const scrapeSel = document.getElementById('scrape-category');
      const filterSel = document.getElementById('filter-category');
      cats.forEach(c => {
        scrapeSel.innerHTML += `<option value="${c}">${c}</option>`;
        filterSel.innerHTML += `<option value="${c}">${c}</option>`;
      });
      loadLeads();
    }

    async function loadLeads() {
      const cat = document.getElementById('filter-category').value;
      const status = document.getElementById('filter-status').value;
      const data = await fetch(`/api/leads?category=${cat}&status=${status}`).then(r => r.json());
      allLeads = data;
      renderTable();
      updateCounts(data);
    }

    function updateCounts(leads) {
      document.getElementById('count-all').textContent = leads.length;
      document.getElementById('count-lead').textContent = leads.filter(l => l.status === 'lead').length;
      document.getElementById('count-review').textContent = leads.filter(l => l.status === 'review').length;
      document.getElementById('count-skipped').textContent = leads.filter(l => l.status === 'skipped').length;
    }

    function setTab(tab) {
      currentTab = tab;
      document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + tab).classList.add('active');
      renderTable();
    }

    function renderTable() {
      const filtered = currentTab === 'all' ? allLeads : allLeads.filter(l => l.status === currentTab);
      const tbody = document.getElementById('leads-body');
      tbody.innerHTML = '';
      filtered.forEach(lead => tbody.appendChild(makeRow(lead)));
    }

    function makeRow(lead) {
      const tr = document.createElement('tr');
      const siteLink = lead.website_url
        ? `<a href="${lead.website_url}" target="_blank">${lead.website_url.replace(/^https?:\/\//, '').slice(0, 30)}</a>`
        : '<em>no website</em>';
      tr.innerHTML = `
        <td>${esc(lead.business_name)}</td>
        <td>${esc(lead.category)}</td>
        <td>${esc(lead.phone)}</td>
        <td>${esc(lead.email)}</td>
        <td>${siteLink}</td>
        <td>${lead.quality_score !== null ? lead.quality_score + '/10' : '—'}</td>
        <td style="max-width:200px;font-size:12px">${esc(lead.quality_notes)}</td>
        <td><input type="text" value="${esc(lead.user_notes)}" onblur="saveNotes(${lead.id}, this.value, '${esc(lead.status)}')" style="width:120px"></td>
        <td>${esc(lead.status)}</td>
        <td>
          <button onclick="setStatus(${lead.id}, 'lead')">Lead</button>
          <button onclick="setStatus(${lead.id}, 'skipped')">Skip</button>
        </td>
      `;
      return tr;
    }

    function esc(str) {
      return (str || '').toString().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    async function setStatus(id, status) {
      await fetch(`/api/leads/${id}?status=${status}`, { method: 'PATCH' });
      loadLeads();
    }

    async function saveNotes(id, notes, status) {
      await fetch(`/api/leads/${id}?status=${status}&user_notes=${encodeURIComponent(notes)}`, { method: 'PATCH' });
    }

    async function startScrape() {
      const category = document.getElementById('scrape-category').value;
      const limit = document.getElementById('scrape-limit').value;
      const resp = await fetch(`/api/scrape?category=${encodeURIComponent(category)}&limit=${limit}`, { method: 'POST' });
      const json = await resp.json();
      if (json.error) { alert(json.error); return; }

      document.getElementById('progress-bar').style.display = 'block';
      if (eventSource) eventSource.close();
      eventSource = new EventSource('/api/stream');

      eventSource.onmessage = (e) => {
        const lead = JSON.parse(e.data);
        allLeads.unshift(lead);
        renderTable();
        updateCounts(allLeads);
      };

      eventSource.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data);
        document.getElementById('progress').max = d.total;
        document.getElementById('progress').value = d.current;
        document.getElementById('status-msg').textContent = d.message;
      });

      eventSource.addEventListener('done', () => {
        eventSource.close();
        document.getElementById('status-msg').textContent = 'Done!';
      });
    }

    function exportCsv() {
      window.location = '/api/export';
    }

    init();
  </script>
</body>
</html>
```

- [ ] **Step 2: Create the static directory and verify the file exists**

```bash
python -c "import os; print(os.path.exists('static/index.html'))"
```

Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: dashboard HTML with live SSE table"
```

---

### Task 10: End-to-End Setup and Smoke Test

**Files:** none — setup and manual verification only

- [ ] **Step 1: Copy .env.example to .env and fill in your keys**

```bash
copy .env.example .env
```

Edit `.env` with your real API keys:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_PLACES_API_KEY=AIza...
YELP_API_KEY=...
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass. If any fail, fix before proceeding.

- [ ] **Step 3: Start the app**

```bash
python main.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 4: Smoke test in the browser**

Open `http://localhost:8000` and verify:
1. Category dropdown is populated with all 6 categories
2. Set limit to `5`, select "coffee shops", click "Run Scrape"
3. Progress bar appears and updates
4. Leads appear in the table one by one as they stream in
5. Click "Visit Site" link on a lead — opens in new tab
6. Click "Lead" on one row — status updates
7. Type a note, click elsewhere — note saves
8. Click "Export CSV" — file downloads with only confirmed leads
9. Check that `leads.db` was created in the project directory

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: complete LA lead finder — ready to use"
```
