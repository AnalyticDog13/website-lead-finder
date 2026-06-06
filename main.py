import asyncio
import csv
import io
import json
import os

import uvicorn
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from models import get_leads, init_db, update_lead_status
from scraper import CATEGORIES, run_scrape_pipeline

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
