from unittest.mock import patch, MagicMock
from scraper import check_website_quality

def test_flags_missing_https():
    result = check_website_quality("http://example.com")
    assert "No HTTPS" in result["flags"]

def test_flags_slow_load():
    mock_response = MagicMock()
    mock_response.text = "<html><head><meta name='viewport' content='width=device-width'></head></html>"

    with patch("scraper.requests.get", return_value=mock_response), \
         patch("scraper.time.time", side_effect=[0, 6]):  # 6 second load
        result = check_website_quality("https://slow-site.com")
    assert "Slow load" in " ".join(result["flags"])

def test_flags_missing_viewport():
    mock_response = MagicMock()
    mock_response.text = "<html><head></head><body></body></html>"

    with patch("scraper.requests.get", return_value=mock_response), \
         patch("scraper.time.time", side_effect=[0, 1]):
        result = check_website_quality("https://example.com")
    assert "No mobile viewport" in result["flags"]

def test_no_flags_for_good_site():
    mock_response = MagicMock()
    mock_response.text = "<html><head><meta name='viewport' content='width=device-width'></head></html>"

    with patch("scraper.requests.get", return_value=mock_response), \
         patch("scraper.time.time", side_effect=[0, 1]):
        result = check_website_quality("https://example.com")
    assert result["flag_count"] == 0

def test_flags_unreachable_site():
    with patch("scraper.requests.get", side_effect=Exception("Connection refused")):
        result = check_website_quality("https://dead-site.com")
    assert any("unreachable" in f.lower() for f in result["flags"])

from scraper import search_google_places

def test_search_google_places_returns_list():
    mock_client = MagicMock()
    mock_client.places.return_value = {
        "results": [{"place_id": "abc123", "name": "Test Barber"}]
    }
    mock_client.place.return_value = {
        "result": {
            "name": "Test Barber",
            "formatted_phone_number": "(310) 555-0001",
            "website": "http://testbarber.com",
            "formatted_address": "123 Main St, Los Angeles CA",
        }
    }

    with patch("scraper.googlemaps.Client", return_value=mock_client), \
         patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake-key"}):
        results = search_google_places("barber shops", limit=1)

    assert len(results) == 1
    assert results[0]["name"] == "Test Barber"
    assert results[0]["phone"] == "(310) 555-0001"
    assert results[0]["website"] == "http://testbarber.com"
    assert results[0]["source"] == "Google"

def test_search_google_places_handles_missing_fields():
    mock_client = MagicMock()
    mock_client.places.return_value = {
        "results": [{"place_id": "abc123"}]
    }
    mock_client.place.return_value = {"result": {}}

    with patch("scraper.googlemaps.Client", return_value=mock_client), \
         patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "fake-key"}):
        results = search_google_places("barber shops", limit=1)

    assert results[0]["phone"] == ""
    assert results[0]["website"] == ""

from scraper import search_yelp

def test_search_yelp_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "businesses": [
            {
                "name": "Silver Lake Coffee",
                "phone": "+13235550001",
                "location": {"display_address": ["123 Sunset Blvd", "Los Angeles, CA 90026"]},
                "url": "https://yelp.com/biz/silver-lake-coffee",
            }
        ]
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

from scraper import score_website_with_ai

def test_score_website_with_ai_returns_score():
    mock_graph = MagicMock()
    mock_graph.run.return_value = {
        "score": 3,
        "notes": "Outdated design, no contact page",
        "email": "owner@example.com",
    }

    with patch("scraper.SmartScraperGraph", return_value=mock_graph), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
        result = score_website_with_ai("https://example.com")

    assert result["score"] == 3
    assert result["email"] == "owner@example.com"
    assert "Outdated" in result["notes"]

def test_score_website_with_ai_handles_failure():
    mock_graph = MagicMock()
    mock_graph.run.side_effect = Exception("LLM error")

    with patch("scraper.SmartScraperGraph", return_value=mock_graph), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
        result = score_website_with_ai("https://example.com")

    assert result["score"] is None
    assert result["email"] == ""

import asyncio
from scraper import deduplicate, process_business, run_scrape_pipeline

def test_deduplicate_removes_same_name():
    businesses = [
        {"name": "Test Barber", "phone": "111", "website": "", "address": "123 Main", "source": "Google"},
        {"name": "test barber", "phone": "222", "website": "", "address": "123 Main", "source": "Yelp"},
        {"name": "Other Shop", "phone": "333", "website": "", "address": "456 Oak", "source": "Yelp"},
    ]
    result = deduplicate(businesses)
    assert len(result) == 2
    assert result[0]["name"] == "Test Barber"

def test_process_business_no_website_is_auto_lead():
    biz = {"name": "No Web Biz", "phone": "111", "website": "", "address": "LA", "source": "Google"}

    with patch("scraper.check_website_quality") as mock_check, \
         patch("scraper.score_website_with_ai") as mock_score, \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "lead"
    assert result.has_website is False
    mock_check.assert_not_called()
    mock_score.assert_not_called()

def test_process_business_two_flags_is_auto_lead():
    biz = {"name": "Bad Site", "phone": "111", "website": "http://bad.com", "address": "LA", "source": "Google"}

    with patch("scraper.check_website_quality", return_value={"flags": ["No HTTPS", "No mobile viewport"], "flag_count": 2}), \
         patch("scraper.score_website_with_ai") as mock_score, \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "lead"
    mock_score.assert_not_called()

def test_process_business_high_ai_score_is_skipped():
    biz = {"name": "Good Site", "phone": "111", "website": "https://good.com", "address": "LA", "source": "Google"}

    with patch("scraper.check_website_quality", return_value={"flags": [], "flag_count": 0}), \
         patch("scraper.score_website_with_ai", return_value={"score": 9, "notes": "Great site", "email": ""}), \
         patch("scraper.insert_lead", return_value=1):
        result = process_business(biz, "barber shop")

    assert result.status == "skipped"

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
            quality_notes="No website", source="Google", address="LA",
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
