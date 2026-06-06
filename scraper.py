import os
import time
import requests
import googlemaps
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
