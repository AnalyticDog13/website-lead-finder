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
