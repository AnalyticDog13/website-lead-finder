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
