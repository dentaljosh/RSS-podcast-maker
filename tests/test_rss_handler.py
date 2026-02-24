import pytest
from unittest.mock import MagicMock
from rss_handler import safe_filename, fetch_article_text


# --- safe_filename tests ---

def test_safe_filename_basic():
    assert safe_filename("Normal Title") == "Normal Title"
    assert safe_filename("Title with / Special @ Characters!") == "Title with  Special  Characters"


def test_safe_filename_trailing_spaces():
    assert safe_filename("Title with space at end ") == "Title with space at end"


def test_safe_filename_alphanumeric():
    assert safe_filename("Episode 123 (Testing)") == "Episode 123 Testing"


def test_safe_filename_dashes_and_dots():
    assert safe_filename("My-Cool_Episode.v1") == "My-Cool_Episode.v1"


# --- fetch_article_text tests (updated to mock httpx) ---

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
    mocker.patch("rss_handler.httpx.get", return_value=mock_response)

    result = fetch_article_text("http://example.com/article")

    assert result is not None
    assert "This is the article text." in result
    assert "ignore this" not in result
    assert "and this" not in result


def test_fetch_article_text_collapses_whitespace(mocker):
    """Extra whitespace is collapsed to single spaces."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"<html><body><p>word1   word2\n\nword3</p></body></html>"
    mocker.patch("rss_handler.httpx.get", return_value=mock_response)

    result = fetch_article_text("http://example.com")
    assert "  " not in result  # no double spaces


def test_fetch_article_text_network_error(mocker):
    """Returns None on a network error."""
    mocker.patch("rss_handler.httpx.get", side_effect=ConnectionError("timeout"))

    result = fetch_article_text("http://example.com")
    assert result is None


def test_fetch_article_text_http_error(mocker):
    """Returns None on an HTTP error status."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")
    mocker.patch("rss_handler.httpx.get", return_value=mock_response)

    result = fetch_article_text("http://example.com")
    assert result is None


def test_fetch_article_text_sends_user_agent(mocker):
    """fetch_article_text passes a User-Agent header."""
    mock_get = mocker.patch("rss_handler.httpx.get", return_value=MagicMock(
        raise_for_status=MagicMock(),
        content=b"<html><body><p>text</p></body></html>",
    ))

    fetch_article_text("http://example.com")

    call_kwargs = mock_get.call_args.kwargs
    assert "headers" in call_kwargs
    assert "User-Agent" in call_kwargs["headers"]
