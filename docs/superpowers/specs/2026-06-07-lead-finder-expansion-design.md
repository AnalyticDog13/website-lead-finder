# Lead Finder Expansion Design

## Goal
Expand the LA Lead Finder to multiple cities, enforce email-only leads with strict placeholder filtering, eliminate mandatory human review, and add an Unreviewed Leads tab with direct export.

---

## 1. Multi-City Architecture

### Data Structure
Replace the flat `LA_NEIGHBORHOODS` list in `scraper.py` with a `CITY_NEIGHBORHOODS` dict:

```python
CITY_NEIGHBORHOODS = {
    "Los Angeles CA": [ ...28 neighborhoods... ],
    "Riverside CA":   [ ...10 neighborhoods... ],
    "Greenville SC":  [ ...10 neighborhoods... ],
    "Boise ID":       [ ...10 neighborhoods... ],
}
CITIES = list(CITY_NEIGHBORHOODS.keys())
```

### Neighborhoods per city
- **Riverside CA:** Downtown Riverside, Canyon Crest, La Sierra, Wood Streets, Victoria, Magnolia Center, University, Arlington, Eastside, Hunter Park
- **Greenville SC:** Downtown Greenville, North Main, Augusta Road, Berea, Sans Souci, Welcome, Taylors, Mauldin, Simpsonville, Greer
- **Boise ID:** Downtown Boise, North End, Bench, East End, Warm Springs, Harris Ranch, Garden City, Meridian, Nampa, Eagle

### API Changes
Two new endpoints replace the single `/api/neighborhoods` endpoint:
- `GET /api/cities` → returns `CITIES` list
- `GET /api/neighborhoods?city=Los+Angeles+CA` → returns `CITY_NEIGHBORHOODS[city]`

The existing `/api/neighborhoods` endpoint is removed.

### UI Changes
The single location dropdown is replaced by two dropdowns:
1. **City dropdown** — populated from `/api/cities`
2. **Neighborhood dropdown** — repopulated from `/api/neighborhoods?city=...` whenever city changes; always has "All neighborhoods (batch)" as the first option

Batch mode works as now: cycles through all neighborhoods for the selected city.

---

## 2. Email Quality Enforcement

### Rule: No email = lead not saved
In `process_business`, after both the website scan and DuckDuckGo fallback run, if `email` is still empty, return `None`. The business is not inserted into the database at all.

### Expanded placeholder domain blocklist
Add to `_SKIP_EMAIL_DOMAINS`:
```python
'contact.com', 'ex.com', 'help.com', 'email.com', 'mail.com',
'domain.com', 'website.com', 'company.com', 'placeholder.com',
'yourwebsite.com', 'yourdomain.com', 'youremail.com', 'acme.com',
'example.org', 'example.net', 'test.com', 'test.org', 'sample.com',
```

### Stricter web search
`_search_web_for_email` currently returns `first_valid` (any email) if no domain-matching email is found. Change: **only return an email if it matches the business's own website domain.** If no domain match, return `''`. This eliminates the main source of placeholder pollution (random emails scraped from unrelated sites in DuckDuckGo results).

For businesses with no website, the web search query is `"{business_name}" "{city}" contact email` and any valid non-blocked email is accepted (there is no domain to match against).

---

## 3. Status Flow + Unreviewed Tab

### New pipeline status
The scraper no longer emits `lead` status. Every lead that passes the email filter enters the DB as `unreviewed`.

Before (in `process_business`):
- No website → `lead`
- Has website → `review`

After:
- Has valid email → `unreviewed`
- No valid email → not saved (return `None`)

The `lead` and `skipped` statuses remain — they are what the user manually assigns when optionally triaging.

### UI tab changes
| Old tab | New tab | Status filter |
|---|---|---|
| Auto-leads | Leads | `lead` |
| Review Queue | Unreviewed Leads | `unreviewed` |
| Skipped | Skipped | `skipped` |
| All | All | all |

### Export changes
- Existing **Export CSV** button exports `status=lead` (manually confirmed, unchanged)
- New **Export Unreviewed** button on the Unreviewed Leads tab exports `status=unreviewed`

### Clear buttons
The "Clear review queue" button label changes to "Clear unreviewed" (same `DELETE /api/leads?status=unreviewed` behavior, was `status=review`).

---

## 4. Files Changed

| File | What changes |
|---|---|
| `scraper.py` | `LA_NEIGHBORHOODS` → `CITY_NEIGHBORHOODS` dict; expand `_SKIP_EMAIL_DOMAINS`; `_search_web_for_email` returns domain-match only (except no-website case); `process_business` status always `unreviewed`, returns `None` if no email |
| `main.py` | Add `GET /api/cities`; change `GET /api/neighborhoods` to accept `?city=` param; add `GET /api/export/unreviewed`; remove old `LA_NEIGHBORHOODS` import |
| `static/index.html` | Two-dropdown city/neighborhood selector; tab rename; Export Unreviewed button; clear button label |
| `tests/test_scraper.py` | Update neighborhood/city tests; update `process_business` tests for new status and no-email skip |
| `tests/test_main.py` | Update neighborhood endpoint test; add cities endpoint test; add export-unreviewed test |

---

## 5. Out of Scope
- Hunter.io / Apollo integration (revisit after seeing email hit rate)
- Per-city neighborhood expansion beyond the 10 listed above
- Any changes to the DB schema (status field already accepts arbitrary strings)
