import asyncio
import csv
import io
import json
import os
from typing import Optional

import uvicorn
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from models import delete_leads_by_status, get_leads, init_db, update_lead_status
from scraper import CATEGORIES, CITIES, CITY_NEIGHBORHOODS, LA_NEIGHBORHOODS, run_batch_pipeline, run_scrape_pipeline

load_dotenv()

_scrape_queue: asyncio.Queue = asyncio.Queue()
_scrape_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(os.getenv("DB_PATH", "leads.db"))
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/categories")
async def categories():
    return CATEGORIES


@app.get("/api/cities")
async def cities():
    return CITIES


@app.get("/api/neighborhoods")
async def neighborhoods(city: str = None):
    if city and city in CITY_NEIGHBORHOODS:
        return CITY_NEIGHBORHOODS[city]
    return LA_NEIGHBORHOODS


@app.post("/api/scrape")
async def start_scrape(category: str, limit: int, location: str = "Los Angeles CA", db_path: str = "leads.db"):
    global _scrape_task, _scrape_queue
    if _scrape_task and not _scrape_task.done():
        return {"error": "Scrape already running"}
    _scrape_queue = asyncio.Queue()
    _scrape_task = asyncio.create_task(
        run_scrape_pipeline(category, limit, _scrape_queue, db_path, location)
    )
    return {"status": "started"}


@app.post("/api/batch")
async def start_batch(category: str, limit: int, city: str = "Los Angeles CA", db_path: str = "leads.db"):
    global _scrape_task, _scrape_queue
    if _scrape_task and not _scrape_task.done():
        return {"error": "Scrape already running"}
    _scrape_queue = asyncio.Queue()
    neighborhoods = CITY_NEIGHBORHOODS.get(city, CITY_NEIGHBORHOODS["Los Angeles CA"])
    _scrape_task = asyncio.create_task(
        run_batch_pipeline(category, limit, _scrape_queue, db_path, neighborhoods, city)
    )
    return {"status": "started", "city": city, "neighborhoods": len(neighborhoods)}


@app.get("/api/stream")
async def stream():
    async def event_generator():
        while True:
            item = await _scrape_queue.get()
            if item["type"] == "done":
                yield "event: done\ndata: {}\n\n"
                break
            elif item["type"] in ("progress", "batch_progress"):
                yield f"event: progress\ndata: {json.dumps(item)}\n\n"
            else:
                yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/leads")
async def get_leads_endpoint(category: str = "all", status: str = "all", db_path: str = "leads.db"):
    return get_leads(db_path=db_path, category=category, status=status)


@app.delete("/api/leads")
async def clear_leads(status: str, db_path: str = "leads.db"):
    count = delete_leads_by_status(status, db_path)
    return {"deleted": count}


@app.patch("/api/leads/{lead_id}")
async def update_lead(
    lead_id: int,
    status: str,
    user_notes: str = None,
    visited: bool = None,
    worth_reaching_out: Optional[bool] = None,
    email: str = None,
    db_path: str = "leads.db",
):
    update_lead_status(lead_id, status, user_notes, visited, worth_reaching_out, email, db_path)
    return {"ok": True}



SETTINGS_FILE = "personal_settings.json"

def _load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {"no_website_template": ""}

def _save_settings(settings: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

@app.get("/api/settings")
async def get_settings():
    return _load_settings()

@app.patch("/api/settings")
async def update_settings(no_website_template: str = ""):
    settings = _load_settings()
    settings["no_website_template"] = no_website_template
    _save_settings(settings)
    return {"ok": True}


@app.get("/api/export")
async def export_csv(db_path: str = "leads.db"):
    leads = get_leads(status="lead", db_path=db_path)
    output = io.StringIO()
    fields = [
        "id", "business_name", "category", "phone", "email",
        "website_url", "has_website", "quality_score", "quality_notes",
        "source", "address", "user_notes", "scraped_at",
        "visited", "worth_reaching_out", "outreach_summary",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(leads)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@app.get("/api/export/unreviewed")
async def export_unreviewed_csv():
    leads = get_leads(status="unreviewed")
    if not leads:
        return Response(content="No unreviewed leads to export.", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["business_name", "category", "phone", "email", "website_url", "address", "source", "scraped_at"])
    writer.writeheader()
    for lead in leads:
        writer.writerow({
            "business_name": lead.business_name,
            "category": lead.category,
            "phone": lead.phone,
            "email": lead.email,
            "website_url": lead.website_url,
            "address": lead.address,
            "source": lead.source,
            "scraped_at": lead.scraped_at,
        })
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=unreviewed_leads.csv"},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
