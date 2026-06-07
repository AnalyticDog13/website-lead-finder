# Lead Finder Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand lead finder to four cities, enforce email-only leads with strict placeholder filtering, remove mandatory review, and add an Unreviewed Leads tab with direct export.

**Architecture:** `scraper.py` gets a city→neighborhoods dict and tighter email rules; `main.py` gets city/neighborhood endpoints and an unreviewed export route; `static/index.html` gets two-dropdown city/neighborhood selection, renamed tabs, and an export-unreviewed button. No DB schema changes — `unreviewed` is just a new status string value.

**Tech Stack:** Python 3.12, FastAPI, SQLite, vanilla JS, requests, BeautifulSoup, DuckDuckGo HTML scraping.

---

## File Map

- Modify: `scraper.py` — city neighborhoods dict, expanded email blocklist, stricter web search, new status logic
- Modify: `main.py` — `/api/cities`, updated `/api/neighborhoods?city=`, `/api/export/unreviewed`
- Modify: `static/index.html` — two dropdowns, tab rename, export-unreviewed button, clear label
- Modify: `tests/test_scraper.py` — updated tests for new city structure and process_business behavior
- Modify: `tests/test_main.py` — updated neighborhood/city/export endpoint tests

---

### Task 1: Replace LA_NEIGHBORHOODS with CITY_NEIGHBORHOODS in scraper.py

**Files:**
- Modify: `scraper.py` (lines 40–67, the `LA_NEIGHBORHOODS` list)
- Modify: `tests/test_scraper.py`

Context: `scraper.py` currently exports `LA_NEIGHBORHOODS` (a flat list). `main.py` imports it as `LA_NEIGHBORHOODS`. We're replacing it with `CITY_NEIGHBORHOODS` (dict) and `CITIES` (list of keys), and keeping a `LA_NEIGHBORHOODS` alias so the batch pipeline internal reference still works until Task 4 updates it.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
from scraper import CITY_NEIGHBORHOODS, CITIES

def test_city_neighborhoods_has_four_cities():
    assert set(CITIES) == {"Los Angeles CA", "Riverside CA", "Greenville SC", "Boise ID"}

def test_each_city_has_neighborhoods():
    for city, hoods in CITY_NEIGHBORHOODS.items():
        assert len(hoods) >= 5, f"{city} has fewer than 5 neighborhoods"

def test_la_neighborhoods_still_accessible():
    # LA_NEIGHBORHOODS alias must still work for backward compat during migration
    from scraper import LA_NEIGHBORHOODS
    assert len(LA_NEIGHBORHOODS) >= 20
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_scraper.py::test_city_neighborhoods_has_four_cities tests/test_scraper.py::test_each_city_has_neighborhoods tests/test_scraper.py::test_la_neighborhoods_still_accessible -v
```

Expected: FAIL (ImportError or AssertionError — `CITY_NEIGHBORHOODS` doesn't exist yet)

- [ ] **Step 3: Replace the LA_NEIGHBORHOODS list in scraper.py**

Remove the existing `LA_NEIGHBORHOODS = [...]` block (lines ~40–67) and replace with:

```python
CITY_NEIGHBORHOODS = {
    "Los Angeles CA": [
        "Silver Lake", "Echo Park", "Koreatown", "Boyle Heights",
        "East Los Angeles", "West Hollywood", "Fairfax", "Crenshaw",
        "Leimert Park", "Inglewood", "Compton", "Watts", "Hawthorne",
        "Torrance", "Long Beach", "Culver City", "Palms", "Mar Vista",
        "Venice", "Santa Monica", "Westchester", "Van Nuys",
        "North Hollywood", "Reseda", "Chatsworth", "Burbank",
        "Glendale", "Pasadena",
    ],
    "Riverside CA": [
        "Downtown Riverside", "Canyon Crest", "La Sierra", "Wood Streets",
        "Victoria", "Magnolia Center", "University", "Arlington",
        "Eastside", "Hunter Park",
    ],
    "Greenville SC": [
        "Downtown Greenville", "North Main", "Augusta Road", "Berea",
        "Sans Souci", "Welcome", "Taylors", "Mauldin", "Simpsonville", "Greer",
    ],
    "Boise ID": [
        "Downtown Boise", "North End", "Bench", "East End", "Warm Springs",
        "Harris Ranch", "Garden City", "Meridian", "Nampa", "Eagle",
    ],
}

CITIES = list(CITY_NEIGHBORHOODS.keys())
LA_NEIGHBORHOODS = CITY_NEIGHBORHOODS["Los Angeles CA"]  # backward-compat alias
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_scraper.py::test_city_neighborhoods_has_four_cities tests/test_scraper.py::test_each_city_has_neighborhoods tests/test_scraper.py::test_la_neighborhoods_still_accessible -v
```

Expected: 3 PASS

- [ ] **Step 5: Run full suite to confirm nothing broke**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```
git add scraper.py tests/test_scraper.py
git commit -m "feat: replace LA_NEIGHBORHOODS with CITY_NEIGHBORHOODS dict for multi-city support"
```

---

### Task 2: Update main.py — cities endpoint + city-aware neighborhoods endpoint

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

Context: `main.py` currently has `GET /api/neighborhoods` returning the flat LA list, imported as `LA_NEIGHBORHOODS`. We're adding `GET /api/cities` and making `/api/neighborhoods` accept a `?city=` query param. The old flat behavior (no param) defaults to LA for backward compat.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_main.py`:

```python
def test_get_cities():
    response = client.get("/api/cities")
    assert response.status_code == 200
    cities = response.json()
    assert "Los Angeles CA" in cities
    assert "Riverside CA" in cities
    assert "Greenville SC" in cities
    assert "Boise ID" in cities

def test_get_neighborhoods_for_city():
    response = client.get("/api/neighborhoods?city=Riverside+CA")
    assert response.status_code == 200
    hoods = response.json()
    assert "Downtown Riverside" in hoods

def test_get_neighborhoods_defaults_to_la():
    response = client.get("/api/neighborhoods")
    assert response.status_code == 200
    hoods = response.json()
    assert "Silver Lake" in hoods
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_main.py::test_get_cities tests/test_main.py::test_get_neighborhoods_for_city tests/test_main.py::test_get_neighborhoods_defaults_to_la -v
```

Expected: FAIL (404 or wrong data)

- [ ] **Step 3: Update main.py imports and endpoints**

Change the import line from:
```python
from scraper import CATEGORIES, LA_NEIGHBORHOODS, run_batch_pipeline, run_scrape_pipeline
```
to:
```python
from scraper import CATEGORIES, CITIES, CITY_NEIGHBORHOODS, run_batch_pipeline, run_scrape_pipeline
```

Replace the existing `/api/neighborhoods` endpoint:
```python
@app.get("/api/cities")
async def cities_endpoint():
    return CITIES


@app.get("/api/neighborhoods")
async def neighborhoods_endpoint(city: str = "Los Angeles CA"):
    return CITY_NEIGHBORHOODS.get(city, CITY_NEIGHBORHOODS["Los Angeles CA"])
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_main.py::test_get_cities tests/test_main.py::test_get_neighborhoods_for_city tests/test_main.py::test_get_neighborhoods_defaults_to_la -v
```

Expected: 3 PASS

- [ ] **Step 5: Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```
git add main.py tests/test_main.py
git commit -m "feat: add /api/cities and city-aware /api/neighborhoods endpoint"
```

---

### Task 3: Expand email blocklist + stricter web search in scraper.py

**Files:**
- Modify: `scraper.py`
- Modify: `tests/test_scraper.py`

Context: `_SKIP_EMAIL_DOMAINS` needs more generic/placeholder domains. `_search_web_for_email` currently returns `first_valid` (any email) as a fallback — we're removing that so it only returns domain-matched emails (except for no-website businesses where any valid email is accepted).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
from scraper import _is_valid_email, _search_web_for_email

def test_blocks_placeholder_domains():
    assert not _is_valid_email("info@contact.com")
    assert not _is_valid_email("me@help.com")
    assert not _is_valid_email("example@ex.com")
    assert not _is_valid_email("hi@domain.com")
    assert not _is_valid_email("test@test.com")
    assert not _is_valid_email("owner@placeholder.com")

def test_accepts_real_business_email():
    assert _is_valid_email("owner@mikes-plumbing.com")
    assert _is_valid_email("contact@elitemedspa.com")
    assert _is_valid_email("info@joesbarber.net")

def test_web_search_only_returns_domain_match():
    # When business has a website, web search should only return emails matching that domain
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Page contains a domain-matching email AND a random one
    mock_resp.text = "contact us at owner@mybiz.com or info@randomsite.com"
    with patch("scraper.requests.get", return_value=mock_resp):
        result = _search_web_for_email("My Biz", "https://mybiz.com")
    assert result == "owner@mybiz.com"

def test_web_search_returns_empty_without_domain_match():
    # When business has a website but only non-domain emails are found, return empty
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "contact info@randomsite.com for help"
    with patch("scraper.requests.get", return_value=mock_resp):
        result = _search_web_for_email("My Biz", "https://mybiz.com")
    assert result == ""

def test_web_search_no_website_accepts_any_valid_email():
    # No website = no domain to match against, accept any valid email
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "reach them at owner@someplace.com"
    with patch("scraper.requests.get", return_value=mock_resp):
        result = _search_web_for_email("My Biz", "")
    assert result == "owner@someplace.com"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_scraper.py::test_blocks_placeholder_domains tests/test_scraper.py::test_accepts_real_business_email tests/test_scraper.py::test_web_search_only_returns_domain_match tests/test_scraper.py::test_web_search_returns_empty_without_domain_match tests/test_scraper.py::test_web_search_no_website_accepts_any_valid_email -v
```

Expected: `test_blocks_placeholder_domains` and web search tests FAIL

- [ ] **Step 3: Expand _SKIP_EMAIL_DOMAINS in scraper.py**

Replace the current `_SKIP_EMAIL_DOMAINS` set:
```python
_SKIP_EMAIL_DOMAINS = {
    'example.com', 'example.org', 'example.net',
    'sentry.io', 'wixpress.com', 'squarespace.com',
    'wordpress.org', 'w3.org', 'schema.org', 'jquery.com', 'googleapis.com',
    'cloudflare.com', 'bootstrapcdn.com', 'fontawesome.com', 'gstatic.com',
    'contact.com', 'ex.com', 'help.com', 'email.com', 'mail.com',
    'domain.com', 'website.com', 'company.com', 'placeholder.com',
    'yourwebsite.com', 'yourdomain.com', 'youremail.com', 'acme.com',
    'test.com', 'test.org', 'sample.com',
}
```

- [ ] **Step 4: Rewrite _search_web_for_email in scraper.py**

Replace the entire `_search_web_for_email` function:

```python
def _search_web_for_email(business_name: str, website_url: str) -> str:
    """
    Search DuckDuckGo for a contact email.
    With a website: only returns emails matching the business's own domain.
    Without a website: accepts any valid non-blocked email.
    """
    domain = ''
    if website_url:
        try:
            domain = urlparse(website_url).netloc.lstrip('www.')
        except Exception:
            pass

    queries = []
    if domain:
        queries.append(f'{business_name} {domain} contact email')
    queries.append(f'"{business_name}" contact email')

    for query in queries:
        try:
            resp = requests.get(
                'https://html.duckduckgo.com/html/',
                params={'q': query},
                headers={**_HEADERS, 'Accept': 'text/html'},
                timeout=5,
            )
            if resp.status_code != 200:
                continue

            for e in _EMAIL_RE.findall(resp.text):
                e = e.lower().rstrip('.')
                if not _is_valid_email(e):
                    continue
                if domain:
                    # Has website: must match the business's domain
                    if e.endswith('@' + domain):
                        return e
                else:
                    # No website: accept any valid email
                    return e

        except Exception:
            pass

    return ''
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_scraper.py::test_blocks_placeholder_domains tests/test_scraper.py::test_accepts_real_business_email tests/test_scraper.py::test_web_search_only_returns_domain_match tests/test_scraper.py::test_web_search_returns_empty_without_domain_match tests/test_scraper.py::test_web_search_no_website_accepts_any_valid_email -v
```

Expected: 5 PASS

- [ ] **Step 6: Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```
git add scraper.py tests/test_scraper.py
git commit -m "feat: expand email blocklist and restrict web search to domain-matched emails"
```

---

### Task 4: process_business — email-required, status always unreviewed

**Files:**
- Modify: `scraper.py` (the `process_business` function)
- Modify: `tests/test_scraper.py`

Context: Currently `process_business` sets status to `lead` (no website) or `review` (has website), and always saves the lead. New behavior: status is always `unreviewed`; if no email found after both scans, return `None` (don't save).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
def test_process_business_no_email_returns_none():
    biz = {"name": "No Email Biz", "phone": "111", "website": "https://noemail.com", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper.find_email_on_pages", return_value=""), \
         patch("scraper._search_web_for_email", return_value=""), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")
    assert result is None

def test_process_business_with_email_status_is_unreviewed():
    biz = {"name": "Has Email", "phone": "111", "website": "https://hasemail.com", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper.find_email_on_pages", return_value="owner@hasemail.com"), \
         patch("scraper._search_web_for_email", return_value=""), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")
    assert result is not None
    assert result.status == "unreviewed"
    assert result.email == "owner@hasemail.com"

def test_process_business_no_website_no_email_returns_none():
    biz = {"name": "No Site No Email", "phone": "111", "website": "", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper._search_web_for_email", return_value=""), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")
    assert result is None

def test_process_business_no_website_with_email_is_unreviewed():
    biz = {"name": "No Site Has Email", "phone": "111", "website": "", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper._search_web_for_email", return_value="owner@someplace.com"), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")
    assert result is not None
    assert result.status == "unreviewed"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_scraper.py::test_process_business_no_email_returns_none tests/test_scraper.py::test_process_business_with_email_status_is_unreviewed tests/test_scraper.py::test_process_business_no_website_no_email_returns_none tests/test_scraper.py::test_process_business_no_website_with_email_is_unreviewed -v
```

Expected: FAIL (wrong status, wrong None behavior)

- [ ] **Step 3: Rewrite process_business in scraper.py**

Replace the entire `process_business` function:

```python
def process_business(biz: dict, category: str, db_path: str = "leads.db", progress_callback=None):
    if business_exists(biz["name"], db_path):
        return None

    website = biz.get("website", "")
    has_website = bool(website)
    email = ""

    if has_website:
        if progress_callback:
            progress_callback("email_scan", f"Scanning site for email: {biz['name']}")
        email = find_email_on_pages(website)

    if not email:
        if progress_callback:
            progress_callback("email_scan", f"Web searching for email: {biz['name']}")
        email = _search_web_for_email(biz["name"], website)

    if not email:
        return None  # no email found — skip this business entirely

    lead = Lead(
        business_name=biz["name"],
        category=category,
        phone=biz.get("phone", ""),
        email=email,
        website_url=website,
        has_website=has_website,
        quality_score=None,
        quality_notes="",
        source=biz.get("source", ""),
        address=biz.get("address", ""),
        status="unreviewed",
        user_notes="",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )
    lead.id = insert_lead(lead, db_path)
    return lead
```

- [ ] **Step 4: Remove now-stale tests**

In `tests/test_scraper.py`, remove these tests (they test old behavior):
- `test_process_business_no_website_is_auto_lead`
- `test_process_business_with_website_goes_to_review`
- `test_process_business_scans_for_email`

They are replaced by the four new tests in Step 1.

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_scraper.py::test_process_business_no_email_returns_none tests/test_scraper.py::test_process_business_with_email_status_is_unreviewed tests/test_scraper.py::test_process_business_no_website_no_email_returns_none tests/test_scraper.py::test_process_business_no_website_with_email_is_unreviewed -v
```

Expected: 4 PASS

- [ ] **Step 6: Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```
git add scraper.py tests/test_scraper.py
git commit -m "feat: process_business now requires email — status always unreviewed, no email = skip"
```

---

### Task 5: Add /api/export/unreviewed endpoint in main.py

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

Context: The existing `/api/export` exports `status=lead`. We need a second export for `status=unreviewed`. Same CSV format, different status filter.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
def test_export_unreviewed_csv():
    with override_settings(db_path=DB_PATH):
        # Insert an unreviewed lead
        lead = Lead(
            business_name="Unreviewed Co", category="plumbing companies",
            phone="555-0001", email="owner@unreviewedco.com",
            website_url="https://unreviewedco.com", has_website=True,
            quality_score=None, quality_notes="", source="Google",
            address="123 Main", status="unreviewed", user_notes="",
            scraped_at="2026-06-07T00:00:00+00:00",
        )
        insert_lead(lead, DB_PATH)
        response = client.get(f"/api/export/unreviewed?db_path={DB_PATH}")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "Unreviewed Co" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_main.py::test_export_unreviewed_csv -v
```

Expected: FAIL (404)

- [ ] **Step 3: Add the endpoint to main.py**

Add after the existing `/api/export` endpoint:

```python
@app.get("/api/export/unreviewed")
async def export_unreviewed_csv(db_path: str = "leads.db"):
    leads = get_leads(status="unreviewed", db_path=db_path)
    output = io.StringIO()
    fields = [
        "id", "business_name", "category", "phone", "email",
        "website_url", "has_website", "source", "address",
        "user_notes", "scraped_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(leads)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=unreviewed_leads.csv"},
    )
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_main.py::test_export_unreviewed_csv -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```
pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```
git add main.py tests/test_main.py
git commit -m "feat: add /api/export/unreviewed endpoint"
```

---

### Task 6: Update static/index.html — two-dropdown city/neighborhood selector, tab rename, export-unreviewed button

**Files:**
- Modify: `static/index.html`

Context: The current UI has a single `<select id="scrape-location">` populated with LA neighborhoods. We need a city dropdown + a neighborhood dropdown that repopulates when city changes. The "Review Queue" tab becomes "Unreviewed Leads". A second export button is added on that tab.

This is a pure frontend task — no backend changes, no tests. Verify by running the server and clicking through the UI.

- [ ] **Step 1: Replace the location dropdown with city + neighborhood dropdowns**

In the Run Scrape row, replace:
```html
<select id="scrape-location" style="width:230px"></select>
```
with:
```html
<select id="scrape-city" style="width:160px" onchange="loadNeighborhoods()"></select>
<select id="scrape-neighborhood" style="width:200px"></select>
```

- [ ] **Step 2: Update the init() function**

Replace the `init()` function body — remove the old neighborhoods fetch, add cities fetch and two-stage population:

```javascript
async function init() {
  const [cats, cities] = await Promise.all([
    fetch('/api/categories').then(r => r.json()),
    fetch('/api/cities').then(r => r.json()),
  ]);

  const catSel = document.getElementById('scrape-category');
  const filterSel = document.getElementById('filter-category');
  cats.forEach(c => {
    catSel.innerHTML += `<option value="${c}">${c}</option>`;
    filterSel.innerHTML += `<option value="${c}">${c}</option>`;
  });

  const citySel = document.getElementById('scrape-city');
  cities.forEach(c => {
    citySel.innerHTML += `<option value="${c}">${c}</option>`;
  });

  await loadNeighborhoods();
  loadLeads();
}
```

- [ ] **Step 3: Add the loadNeighborhoods() function**

Add after `init()`:

```javascript
async function loadNeighborhoods() {
  const city = document.getElementById('scrape-city').value;
  const hoods = await fetch(`/api/neighborhoods?city=${encodeURIComponent(city)}`).then(r => r.json());
  const sel = document.getElementById('scrape-neighborhood');
  sel.innerHTML = `<option value="__batch__">All neighborhoods (batch)</option>
    <option disabled>──────────────</option>`;
  hoods.forEach(h => {
    sel.innerHTML += `<option value="${h}">${h}</option>`;
  });
}
```

- [ ] **Step 4: Update startScrape() to use the new dropdowns**

Replace the location reading in `startScrape()`:
```javascript
// OLD:
const location = document.getElementById('scrape-location').value;
const isBatch = location === '__batch__';
```
with:
```javascript
const city = document.getElementById('scrape-city').value;
const neighborhood = document.getElementById('scrape-neighborhood').value;
const isBatch = neighborhood === '__batch__';
const location = isBatch ? city : `${neighborhood} ${city}`;
```

And update the batch fetch to pass city as a query param so the server knows which neighborhood list to use — update the batch POST:
```javascript
resp = await fetch(`/api/batch?category=${encodeURIComponent(category)}&limit=${limit}&city=${encodeURIComponent(city)}`, { method: 'POST' });
```

- [ ] **Step 5: Update main.py /api/batch to accept city param**

In `main.py`, update the `/api/batch` endpoint to accept `city` and pass it to `run_batch_pipeline`:

```python
@app.post("/api/batch")
async def start_batch(category: str, limit: int, city: str = "Los Angeles CA", db_path: str = "leads.db"):
    global _scrape_task, _scrape_queue
    if _scrape_task and not _scrape_task.done():
        return {"error": "Scrape already running"}
    _scrape_queue = asyncio.Queue()
    neighborhoods = CITY_NEIGHBORHOODS.get(city, CITY_NEIGHBORHOODS["Los Angeles CA"])
    _scrape_task = asyncio.create_task(
        run_batch_pipeline(category, limit, _scrape_queue, db_path, neighborhoods)
    )
    return {"status": "started", "city": city, "neighborhoods": len(neighborhoods)}
```

- [ ] **Step 6: Rename the Review Queue tab to Unreviewed Leads**

In the tabs section of `index.html`, change:
```html
<button onclick="setTab('review')" id="tab-review">Review Queue (<span id="count-review">0</span>)</button>
```
to:
```html
<button onclick="setTab('unreviewed')" id="tab-unreviewed">Unreviewed Leads (<span id="count-unreviewed">0</span>)</button>
```

And update `updateCounts()`:
```javascript
function updateCounts(leads) {
  document.getElementById('count-all').textContent = leads.length;
  document.getElementById('count-lead').textContent = leads.filter(l => l.status === 'lead').length;
  document.getElementById('count-unreviewed').textContent = leads.filter(l => l.status === 'unreviewed').length;
  document.getElementById('count-skipped').textContent = leads.filter(l => l.status === 'skipped').length;
}
```

- [ ] **Step 7: Add Export Unreviewed button and update Clear button label**

In the scrape control row, the existing export button stays. Add a second export button next to it:
```html
<button onclick="exportUnreviewed()">&#8595; Export Unreviewed</button>
```

Add the function:
```javascript
function exportUnreviewed() {
  window.location = '/api/export/unreviewed';
}
```

In the clear buttons section, update the label:
```html
<button onclick="clearStatus('unreviewed')" style="font-size:12px;color:#a00;border-color:#a00">&#x1F5D1; Clear unreviewed</button>
```

And update the `clearStatus` function — the label text:
```javascript
const label = status === 'unreviewed' ? 'unreviewed leads' : status;
```

- [ ] **Step 8: Update the status dropdown filter**

In the filter section, change:
```html
<option value="review">Review Queue</option>
```
to:
```html
<option value="unreviewed">Unreviewed</option>
```

- [ ] **Step 9: Smoke-test the UI**

```
python main.py
```

Open `http://localhost:8000` and verify:
- City dropdown shows 4 cities
- Switching city repopulates neighborhood dropdown
- "All neighborhoods (batch)" is always the first neighborhood option
- "Unreviewed Leads" tab exists and works
- "Export Unreviewed" button downloads a CSV
- "Clear unreviewed" button prompts and deletes

- [ ] **Step 10: Commit**

```
git add static/index.html main.py
git commit -m "feat: two-dropdown city/neighborhood UI, Unreviewed Leads tab, export-unreviewed button"
```

---

### Task 7: Update run_batch_pipeline signature + remove LA_NEIGHBORHOODS import from main.py

**Files:**
- Modify: `scraper.py` (the `run_batch_pipeline` function default arg)
- Modify: `main.py` (import cleanup)

Context: `run_batch_pipeline` currently defaults to `LA_NEIGHBORHOODS` internally. Since Task 6 now passes the correct neighborhood list from the API, the default can point to the full dict. Also clean up any lingering `LA_NEIGHBORHOODS` references in main.py.

- [ ] **Step 1: Update run_batch_pipeline default in scraper.py**

The function signature currently is:
```python
async def run_batch_pipeline(
    category: str,
    limit: int,
    queue: asyncio.Queue,
    db_path: str = "leads.db",
    neighborhoods: list = None,
):
    if neighborhoods is None:
        neighborhoods = LA_NEIGHBORHOODS
```

The `LA_NEIGHBORHOODS` alias still works (from Task 1), so this is fine as-is. No change needed here — the alias covers it.

- [ ] **Step 2: Verify main.py doesn't import LA_NEIGHBORHOODS**

Check the import line in `main.py`:
```python
from scraper import CATEGORIES, CITIES, CITY_NEIGHBORHOODS, run_batch_pipeline, run_scrape_pipeline
```

If `LA_NEIGHBORHOODS` appears anywhere in `main.py`, remove it.

- [ ] **Step 3: Run full suite one final time**

```
pytest tests/ -v
```

Expected: all pass

- [ ] **Step 4: Final commit**

```
git add scraper.py main.py
git commit -m "chore: clean up LA_NEIGHBORHOODS references, verify multi-city pipeline wiring"
```
