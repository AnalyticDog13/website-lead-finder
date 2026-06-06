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
