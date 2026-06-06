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
