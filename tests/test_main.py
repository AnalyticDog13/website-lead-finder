import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GOOGLE_PLACES_API_KEY", "fake")
os.environ.setdefault("YELP_API_KEY", "fake")

from main import app
from models import init_db, insert_lead, Lead
from datetime import datetime, timezone

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
        status="review", user_notes="", scraped_at=datetime.now(timezone.utc).isoformat(),
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

def test_get_cities_returns_list():
    response = client.get("/api/cities")
    assert response.status_code == 200
    data = response.json()
    assert "cities" in data
    assert set(data["cities"]) == {"Los Angeles CA", "Riverside CA", "Greenville SC", "Boise ID"}

def test_get_neighborhoods_default_returns_la():
    response = client.get("/api/neighborhoods")
    assert response.status_code == 200
    data = response.json()
    assert "neighborhoods" in data
    assert len(data["neighborhoods"]) >= 20

def test_get_neighborhoods_with_city_param():
    response = client.get("/api/neighborhoods?city=Riverside+CA")
    assert response.status_code == 200
    data = response.json()
    assert "neighborhoods" in data
    assert "Downtown Riverside" in data["neighborhoods"]

def test_get_neighborhoods_unknown_city_returns_la():
    response = client.get("/api/neighborhoods?city=Unknown+City")
    assert response.status_code == 200
    data = response.json()
    assert len(data["neighborhoods"]) >= 20
