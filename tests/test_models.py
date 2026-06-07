import os
import pytest
from models import Lead, init_db, insert_lead, get_leads, update_lead_status, business_exists

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
    insert_lead(make_lead(business_name="Other", status="review"), DB_PATH)
    leads = get_leads(status="lead", db_path=DB_PATH)
    assert len(leads) == 1
    assert leads[0]["status"] == "lead"

def test_get_leads_filters_by_category():
    insert_lead(make_lead(category="barber shop"), DB_PATH)
    insert_lead(make_lead(business_name="Other", category="coffee shop"), DB_PATH)
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

def test_update_lead_visited():
    lead_id = insert_lead(make_lead(), DB_PATH)
    update_lead_status(lead_id, "review", visited=True, db_path=DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert leads[0]["visited"] == 1

def test_update_lead_worth_reaching_out():
    lead_id = insert_lead(make_lead(), DB_PATH)
    update_lead_status(lead_id, "review", worth_reaching_out=True, db_path=DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert leads[0]["worth_reaching_out"] == 1

def test_insert_lead_deduplicates_by_name():
    lead = make_lead(business_name="Silver Lake Cuts")
    id1 = insert_lead(lead, DB_PATH)
    id2 = insert_lead(make_lead(business_name="Silver Lake Cuts", category="coffee shop"), DB_PATH)
    assert id1 == id2
    leads = get_leads(db_path=DB_PATH)
    assert len(leads) == 1

def test_insert_lead_deduplicates_case_insensitive():
    insert_lead(make_lead(business_name="Echo Park Coffee"), DB_PATH)
    insert_lead(make_lead(business_name="echo park coffee"), DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert len(leads) == 1

def test_business_exists_true():
    insert_lead(make_lead(business_name="Known Barber"), DB_PATH)
    assert business_exists("Known Barber", DB_PATH) is True

def test_business_exists_false():
    assert business_exists("Unknown Shop", DB_PATH) is False

def test_leads_include_visited_and_worth_fields():
    insert_lead(make_lead(), DB_PATH)
    leads = get_leads(db_path=DB_PATH)
    assert "visited" in leads[0]
    assert "worth_reaching_out" in leads[0]
