import pytest
from unittest.mock import MagicMock, patch
from rss_handler import safe_filename, fetch_article_text


# --- safe_filename tests (existing) ---

def test_safe_filename_basic():
    assert safe_filename("Normal Title") == "Normal Title"
    assert safe_filename("Title with / Special @ Characters!") == "Title with  Special  Characters"

def test_safe_filename_trailing_spaces():
    assert safe_filename("Title with space at end ") == "Title with space at end"

def test_safe_filename_alphanumeric():
    assert safe_filename("Episode 123 (Testing)") == "Episode 123 Testing"

def test_safe_filename_dashes_and_dots():
    assert safe_filename("My-Cool_Episode.v1") == "My-Cool_Episode.v1"


# --- fetch_article_text tests ---

def test_fetch_article_text_success(mocker):
    """Returns cleaned text when the request succeeds."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"""
        <html><body>
            <script>ignore this</script>
            <style>and this</style>
            <p>  This   is    the article text.  </p>
        </body></html>
    """
    mocker.patch("rss_handler.requests.get", return_value=mock_response)

    result = fetch_article_text("http://example.com/article")

    assert result is not None
    assert "This is the article text." in result
    # Script and style tags should be stripped
    assert "ignore this" not in result
    assert "and this" not in result


def test_fetch_article_text_collapses_whitespace(mocker):
    """Extra whitespace is collapsed to single spaces."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"<html><body><p>word1   word2\n\nword3</p></body></html>"
    mocker.patch("rss_handler.requests.get", return_value=mock_response)

    result = fetch_article_text("http://example.com")
    assert "  " not in result  # no double spaces


def test_fetch_article_text_network_error(mocker):
    """Returns None on a network error."""
    mocker.patch("rss_handler.requests.get", side_effect=ConnectionError("timeout"))

    result = fetch_article_text("http://example.com")
    assert result is None


def test_fetch_article_text_http_error(mocker):
    """Returns None on an HTTP error status."""
    import requests as req
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("404")
    mocker.patch("rss_handler.requests.get", return_value=mock_response)

    result = fetch_article_text("http://example.com")
    assert result is None
