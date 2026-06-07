import asyncio
from unittest.mock import patch, MagicMock

from scraper import (
    find_email_on_pages,
    search_google_places,
    search_yelp,
    deduplicate,
    process_business,
    run_scrape_pipeline,
)
from scraper import CITY_NEIGHBORHOODS, CITIES


def test_city_neighborhoods_has_four_cities():
    assert set(CITIES) == {"Los Angeles CA", "Riverside CA", "Greenville SC", "Boise ID"}

def test_each_city_has_neighborhoods():
    for city, hoods in CITY_NEIGHBORHOODS.items():
        assert len(hoods) >= 5, f"{city} has fewer than 5 neighborhoods"

def test_la_neighborhoods_still_accessible():
    from scraper import LA_NEIGHBORHOODS
    assert len(LA_NEIGHBORHOODS) >= 20


# --- find_email_on_pages ---

def test_find_email_on_pages_finds_mailto():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '<a href="mailto:owner@testshop.com">Contact</a>'
    with patch("scraper.requests.get", return_value=mock_response):
        result = find_email_on_pages("https://testshop.com")
    assert result == "owner@testshop.com"

def test_find_email_on_pages_falls_back_to_regex():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Email us at hello@example.net for more info"
    with patch("scraper.requests.get", return_value=mock_response):
        result = find_email_on_pages("https://testshop.com")
    assert result == "hello@example.net"

def test_find_email_on_pages_skips_junk_domains():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "track@sentry.io noreply@example.com real@mybiz.com"
    with patch("scraper.requests.get", return_value=mock_response):
        result = find_email_on_pages("https://testshop.com")
    assert result == "real@mybiz.com"

def test_find_email_on_pages_returns_empty_when_none():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<p>No contact info here</p>"
    with patch("scraper.requests.get", return_value=mock_response):
        result = find_email_on_pages("https://testshop.com")
    assert result == ""


# --- search_google_places ---

def test_search_google_places_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "places": [{
            "displayName": {"text": "Test Barber"},
            "nationalPhoneNumber": "(310) 555-0001",
            "websiteUri": "http://testbarber.com",
            "formattedAddress": "123 Main St, Los Angeles CA",
        }]
    }
    with patch("scraper.requests.post", return_value=mock_response), \
         patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake-key"}):
        results = search_google_places("barber shops", limit=1)

    assert len(results) == 1
    assert results[0]["name"] == "Test Barber"
    assert results[0]["phone"] == "(310) 555-0001"
    assert results[0]["website"] == "http://testbarber.com"
    assert results[0]["source"] == "Google"

def test_search_google_places_handles_missing_fields():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "places": [{"displayName": {"text": "Bare Minimum Shop"}}]
    }
    with patch("scraper.requests.post", return_value=mock_response), \
         patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake-key"}):
        results = search_google_places("barber shops", limit=1)

    assert results[0]["phone"] == ""
    assert results[0]["website"] == ""


# --- search_yelp ---

def test_search_yelp_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "businesses": [{
            "name": "Silver Lake Coffee",
            "phone": "+13235550001",
            "location": {"display_address": ["123 Sunset Blvd", "Los Angeles, CA 90026"]},
        }]
    }
    with patch("scraper.requests.get", return_value=mock_response), \
         patch.dict("os.environ", {"YELP_API_KEY": "fake-key"}):
        results = search_yelp("coffee shops", limit=1)

    assert len(results) == 1
    assert results[0]["name"] == "Silver Lake Coffee"
    assert results[0]["phone"] == "+13235550001"
    assert results[0]["source"] == "Yelp"

def test_search_yelp_handles_empty_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {"businesses": []}
    with patch("scraper.requests.get", return_value=mock_response), \
         patch.dict("os.environ", {"YELP_API_KEY": "fake-key"}):
        results = search_yelp("coffee shops", limit=10)

    assert results == []


# --- deduplicate ---

def test_deduplicate_removes_same_name():
    businesses = [
        {"name": "Test Barber", "phone": "111", "website": "", "address": "123 Main", "source": "Google"},
        {"name": "test barber", "phone": "222", "website": "", "address": "123 Main", "source": "Yelp"},
        {"name": "Other Shop", "phone": "333", "website": "", "address": "456 Oak", "source": "Yelp"},
    ]
    result = deduplicate(businesses)
    assert len(result) == 2
    assert result[0]["name"] == "Test Barber"


# --- process_business ---

def test_process_business_no_website_is_auto_lead():
    biz = {"name": "No Web Biz", "phone": "111", "website": "", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper.find_email_on_pages") as mock_email, \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "lead"
    assert result.has_website is False
    mock_email.assert_not_called()

def test_process_business_with_website_goes_to_review():
    biz = {"name": "Has Site", "phone": "111", "website": "https://hassite.com", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper.find_email_on_pages", return_value=""), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "review"
    assert result.has_website is True

def test_process_business_scans_for_email():
    biz = {"name": "Email Biz", "phone": "111", "website": "https://emailbiz.com", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=False), \
         patch("scraper.find_email_on_pages", return_value="found@emailbiz.com"), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.email == "found@emailbiz.com"

def test_process_business_skips_duplicate():
    biz = {"name": "Already There", "phone": "111", "website": "", "address": "LA", "source": "Google"}
    with patch("scraper.business_exists", return_value=True):
        result = process_business(biz, "barber shop")

    assert result is None


# --- run_scrape_pipeline ---

def test_run_scrape_pipeline_streams_leads():
    biz = {"name": "Test", "phone": "111", "website": "", "address": "LA", "source": "Google"}
    with patch("scraper.search_google_places", return_value=[biz]), \
         patch("scraper.search_yelp", return_value=[]), \
         patch("scraper.process_business") as mock_process, \
         patch("scraper.insert_lead", return_value=1):

        from models import Lead
        from datetime import datetime, timezone
        mock_lead = Lead(
            business_name="Test", category="barber shop", phone="111",
            email="", website_url="", has_website=False, quality_score=None,
            quality_notes="", source="Google", address="LA",
            status="lead", user_notes="", scraped_at=datetime.now(timezone.utc).isoformat(), id=1,
        )
        mock_process.return_value = mock_lead

        queue = asyncio.Queue()
        asyncio.run(run_scrape_pipeline("barber shop", 1, queue))

        items = []
        while not queue.empty():
            items.append(queue.get_nowait())

    types = [i["type"] for i in items]
    assert "lead" in types
    assert "done" in types

def test_run_scrape_pipeline_skips_none_leads():
    biz = {"name": "Duplicate Biz", "phone": "111", "website": "", "address": "LA", "source": "Google"}
    with patch("scraper.search_google_places", return_value=[biz]), \
         patch("scraper.search_yelp", return_value=[]), \
         patch("scraper.process_business", return_value=None):

        queue = asyncio.Queue()
        asyncio.run(run_scrape_pipeline("barber shop", 1, queue))

        items = []
        while not queue.empty():
            items.append(queue.get_nowait())

    types = [i["type"] for i in items]
    assert "lead" not in types
    assert "done" in types
