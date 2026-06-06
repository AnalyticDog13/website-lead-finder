import asyncio
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone

import requests
import googlemaps
from bs4 import BeautifulSoup
from scrapegraphai.graphs import SmartScraperGraph

from models import Lead, insert_lead

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


def search_google_places(category: str, limit: int, location: str = "Los Angeles CA") -> list:
    gmaps = googlemaps.Client(key=os.getenv("GOOGLE_PLACES_API_KEY"))
    results = []
    query = f"{category} in {location}"
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


def search_yelp(category: str, limit: int, location: str = "Los Angeles, CA") -> list:
    headers = {"Authorization": f"Bearer {os.getenv('YELP_API_KEY')}"}
    params = {
        "term": category,
        "location": location,
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
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )
    lead.id = insert_lead(lead, db_path)
    return lead


async def run_scrape_pipeline(category: str, limit: int, queue: asyncio.Queue, db_path: str = "leads.db", location: str = "Los Angeles CA"):
    google_results = await asyncio.to_thread(search_google_places, category, limit, location)
    yelp_results = await asyncio.to_thread(search_yelp, category, limit, location) if os.getenv("YELP_API_KEY") else []

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
