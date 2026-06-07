import asyncio
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from models import Lead, business_exists, insert_lead

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_SKIP_EMAIL_DOMAINS = {
    'example.com', 'sentry.io', 'wixpress.com', 'squarespace.com',
    'wordpress.org', 'w3.org', 'schema.org', 'jquery.com', 'googleapis.com',
    'cloudflare.com', 'bootstrapcdn.com', 'fontawesome.com', 'gstatic.com',
    'contact.com', 'ex.com', 'help.com', 'email.com', 'mail.com',
    'domain.com', 'website.com', 'company.com', 'placeholder.com',
    'yourwebsite.com', 'yourdomain.com', 'youremail.com', 'acme.com',
    'example.org', 'example.net', 'test.com', 'test.org', 'sample.com',
}
_SKIP_EMAIL_PREFIXES = ('noreply', 'no-reply', 'donotreply', 'bounce', 'mailer-daemon', 'postmaster', 'webmaster')

CATEGORIES = [
    "photographers",
    "coffee shops",
    "barber shops",
    "freelancers",
    "real estate agents",
    "workout yoga studios",
    "moving companies",
    "lawn services",
    "bike repair shops",
    "watch repair shops",
    "roofing companies",
    "construction contractors",
    "med spas",
    "plumbing companies",
    "landscapers",
]

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

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}



def _decode_cloudflare_email(encoded: str) -> str:
    """Decode Cloudflare's data-cfemail obfuscation."""
    try:
        r = int(encoded[:2], 16)
        return ''.join(chr(int(encoded[i:i+2], 16) ^ r) for i in range(2, len(encoded), 2))
    except Exception:
        return ''


def _is_valid_email(email: str) -> bool:
    if '@' not in email or len(email) > 254:
        return False
    prefix, domain = email.rsplit('@', 1)
    if domain in _SKIP_EMAIL_DOMAINS:
        return False
    if prefix.startswith(_SKIP_EMAIL_PREFIXES):
        return False
    if '.' not in domain or domain.endswith(('.png', '.jpg', '.gif', '.js', '.css')):
        return False
    return True


def find_email_on_pages(base_url: str) -> str:
    """
    Scan the main page plus common contact/about/team paths for emails.
    Checks structured data (JSON-LD, itemprop), Cloudflare obfuscation,
    mailto: links, and footer/full-page regex. Returns the highest-confidence
    email found.
    """
    paths = [
        '', '/contact', '/contact-us',
        '/about', '/about-us',
        '/team', '/staff',
        '/get-in-touch', '/connect', '/info',
    ]
    found_structured = []  # JSON-LD / itemprop — most explicit
    found_cf = []           # Cloudflare decoded
    found_mailto = []       # mailto: links
    found_regex = []        # footer regex, then full-page regex

    for path in paths:
        try:
            url = base_url.rstrip('/') + path
            resp = requests.get(url, timeout=5, headers=_HEADERS)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')

            # JSON-LD structured data (schema.org LocalBusiness etc.)
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string or '')
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict):
                            e = str(item.get('email', '')).strip().lower()
                            if e and _is_valid_email(e) and e not in found_structured:
                                found_structured.append(e)
                except Exception:
                    pass

            # itemprop="email" (microdata)
            for el in soup.find_all(attrs={"itemprop": "email"}):
                e = (el.get('content') or el.get_text()).strip().lower()
                if _is_valid_email(e) and e not in found_structured:
                    found_structured.append(e)

            # Cloudflare obfuscation
            for el in soup.find_all(attrs={"data-cfemail": True}):
                e = _decode_cloudflare_email(el['data-cfemail']).lower()
                if _is_valid_email(e) and e not in found_cf:
                    found_cf.append(e)

            # mailto: links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.lower().startswith('mailto:'):
                    e = href[7:].split('?')[0].strip().lower()
                    if _is_valid_email(e) and e not in found_mailto:
                        found_mailto.append(e)

            # Footer-first regex (footer often has cleanest contact info)
            footer = soup.find('footer')
            scan_targets = [footer.get_text() if footer else '', resp.text]
            for text in scan_targets:
                for e in _EMAIL_RE.findall(text):
                    e = e.lower().rstrip('.')
                    if _is_valid_email(e) and e not in found_regex:
                        found_regex.append(e)

        except Exception:
            pass

        # Stop scanning more paths once we have high-confidence results
        if found_structured or found_cf or found_mailto:
            break

    combined = found_structured + found_cf + found_mailto + found_regex
    return combined[0] if combined else ''


def _search_web_for_email(business_name: str, website_url: str) -> str:
    """
    Search DuckDuckGo for a contact email for the business.
    Used as a fallback when the website scan finds nothing.
    If the business has a website, only returns emails matching its domain.
    If no website, accepts any valid non-blocked email.
    """
    domain = ''
    if website_url:
        try:
            domain = urlparse(website_url).netloc.lstrip('www.')
        except Exception:
            pass

    query = f'{business_name} {domain} contact email' if domain else f'"{business_name}" contact email'

    try:
        resp = requests.get(
            'https://html.duckduckgo.com/html/',
            params={'q': query},
            headers={**_HEADERS, 'Accept': 'text/html'},
            timeout=5,
        )
        if resp.status_code != 200:
            return ''

        domain_match = ''
        first_valid = ''
        for e in _EMAIL_RE.findall(resp.text):
            e = e.lower().rstrip('.')
            if not _is_valid_email(e):
                continue
            if domain and e.endswith('@' + domain):
                domain_match = e
                break
            if not first_valid:
                first_valid = e

        if domain_match:
            return domain_match
        if not domain:  # no-website case: accept any valid email
            return first_valid
        return ''  # has website but no domain match: reject

    except Exception:
        return ''



def search_google_places(category: str, limit: int, location: str = "Los Angeles CA") -> list:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    businesses = []
    page_token = None

    while len(businesses) < limit:
        payload = {
            "textQuery": f"{category} in {location}",
            "maxResultCount": min(20, limit - len(businesses)),
        }
        if page_token:
            payload["pageToken"] = page_token

        response = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            json=payload,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,nextPageToken",
            },
        )
        data = response.json()

        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))

        places = data.get("places", [])
        for place in places:
            businesses.append({
                "name": place.get("displayName", {}).get("text", ""),
                "phone": place.get("nationalPhoneNumber", ""),
                "website": place.get("websiteUri", ""),
                "address": place.get("formattedAddress", ""),
                "source": "Google",
            })

        page_token = data.get("nextPageToken")
        if not page_token or not places:
            break

    return businesses[:limit]


def search_yelp(category: str, limit: int, location: str = "Los Angeles, CA") -> list:
    headers = {"Authorization": f"Bearer {os.getenv('YELP_API_KEY')}"}
    params = {"term": category, "location": location, "limit": min(limit, 50)}
    response = requests.get("https://api.yelp.com/v3/businesses/search", headers=headers, params=params)
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


def deduplicate(businesses: list) -> list:
    seen = set()
    unique = []
    for biz in businesses:
        key = biz["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(biz)
    return unique


def process_business(biz: dict, category: str, db_path: str = "leads.db", progress_callback=None):
    if business_exists(biz["name"], db_path):
        return None

    website = biz.get("website", "")
    has_website = bool(website)
    email = ""
    status = "lead" if not has_website else "review"

    if has_website:
        if progress_callback:
            progress_callback("email_scan", f"Scanning site for email: {biz['name']}")
        email = find_email_on_pages(website)

    if not email:
        if progress_callback:
            progress_callback("email_scan", f"Web searching for email: {biz['name']}")
        email = _search_web_for_email(biz["name"], website)

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
        status=status,
        user_notes="",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )
    lead.id = insert_lead(lead, db_path)
    return lead


async def run_scrape_pipeline(
    category: str,
    limit: int,
    queue: asyncio.Queue,
    db_path: str = "leads.db",
    location: str = "Los Angeles CA",
    send_done: bool = True,
):
    await queue.put({
        "type": "progress", "phase": "fetching", "current": 0, "total": limit,
        "message": f"Fetching {category} from Google Places...",
    })

    loop = asyncio.get_event_loop()

    try:
        google_results = await asyncio.to_thread(search_google_places, category, limit, location)
    except Exception as e:
        print(f"[ERROR] Google Places: {e}")
        await queue.put({"type": "error", "message": f"Google Places error: {e}"})
        await queue.put({"type": "done"})
        return

    yelp_results = (
        await asyncio.to_thread(search_yelp, category, limit, location)
        if os.getenv("YELP_API_KEY") else []
    )

    businesses = deduplicate(google_results + yelp_results)[:limit]
    total = len(businesses)

    if total == 0:
        print(f"[WARN] No businesses returned for '{category}' in '{location}'")
        await queue.put({"type": "error", "message": "No businesses found — check your API key and that the Places API is enabled."})
        await queue.put({"type": "done"})
        return

    for i, biz in enumerate(businesses):
        await queue.put({
            "type": "progress", "phase": "processing",
            "current": i + 1, "total": total,
            "message": f"Processing {biz['name']}...",
        })

        def make_phase_callback(idx, tot):
            def callback(phase, message):
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "type": "progress", "phase": phase,
                    "current": idx + 1, "total": tot, "message": message,
                })
            return callback

        try:
            lead = await asyncio.wait_for(
                asyncio.to_thread(
                    process_business, biz, category, db_path, make_phase_callback(i, total)
                ),
                timeout=50,
            )
        except asyncio.TimeoutError:
            await queue.put({"type": "progress", "phase": "processing",
                             "current": i + 1, "total": total,
                             "message": f"Timed out on {biz['name']}, moving on..."})
            continue
        except Exception as e:
            await queue.put({"type": "progress", "phase": "processing",
                             "current": i + 1, "total": total,
                             "message": f"Skipped {biz['name']}: {e}"})
            continue

        if lead is None:
            continue
        await queue.put({"type": "lead", **asdict(lead)})

    if send_done:
        await queue.put({"type": "done"})



async def run_batch_pipeline(
    category: str,
    limit: int,
    queue: asyncio.Queue,
    db_path: str = "leads.db",
    neighborhoods: list = None,
):
    if neighborhoods is None:
        neighborhoods = LA_NEIGHBORHOODS

    total = len(neighborhoods)
    for i, neighborhood in enumerate(neighborhoods):
        location = f"{neighborhood} Los Angeles CA"
        await queue.put({
            "type": "batch_progress",
            "neighborhood": neighborhood,
            "current_neighborhood": i + 1,
            "total_neighborhoods": total,
            "message": f"Neighborhood {i + 1}/{total}: scanning {neighborhood}...",
        })
        await run_scrape_pipeline(category, limit, queue, db_path, location, send_done=False)

    await queue.put({"type": "done"})
