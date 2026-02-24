import pytest
from unittest.mock import MagicMock

from main import process_entry
from db_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Provides a fresh in-memory-like DatabaseManager for each test."""
    return DatabaseManager(db_path=str(tmp_path / "test.db"))


def _make_entry(title="Test Article", link="http://example.com/1", entry_id="id-1"):
    """Builds a minimal feedparser-like entry mock."""
    data = {"id": entry_id, "link": link, "summary": ""}
    e = MagicMock()
    e.title = title
    e.get = lambda key, default=None: data.get(key, default)
    return e


def _default_show(show_id="show-1"):
    return {"id": show_id, "google_drive": {"folder_id": "folder-abc"}}


def _default_gen():
    return {"anthropic_model": "claude-3", "target_length_minutes": 5}


def _default_audio():
    return {"openai_tts_model": "tts-1", "host_a_voice": "alloy", "host_b_voice": "echo"}


# --- Already processed ---

def test_process_entry_skips_already_processed(db):
    """Returns False immediately if the item was already processed."""
    db.mark_processed("show-1", "id-1", title="old")
    entry = _make_entry()
    result = process_entry(
        entry, _default_show(), "Feed", "http://feed.url",
        _default_gen(), _default_audio(),
        MagicMock(), MagicMock(), MagicMock(), db,
    )
    assert result is False


# --- Short article text ---

def test_process_entry_skips_short_article(db, mocker):
    """Returns False if the fetched article text is too short."""
    mocker.patch("main.fetch_article_text", return_value="too short")
    entry = _make_entry()
    result = process_entry(
        entry, _default_show(), "Feed", "http://feed.url",
        _default_gen(), _default_audio(),
        MagicMock(), MagicMock(), MagicMock(), db,
    )
    assert result is False
    assert not db.is_processed("show-1", "id-1")


def test_process_entry_skips_none_article(db, mocker):
    """Returns False if fetch_article_text returns None."""
    mocker.patch("main.fetch_article_text", return_value=None)
    entry = _make_entry()
    entry.get = lambda key, default=None: {"id": "id-1", "link": "http://x.com", "summary": None}.get(key, default)
    result = process_entry(
        entry, _default_show(), "Feed", "http://feed.url",
        _default_gen(), _default_audio(),
        MagicMock(), MagicMock(), MagicMock(), db,
    )
    assert result is False


# --- Full success path ---

def test_process_entry_marks_processed_on_success(db, mocker):
    """On full success, returns True and item is marked in the database."""
    mocker.patch("main.fetch_article_text", return_value="x" * 200)
    mocker.patch("main.generate_script", return_value="HOST_A: Hi\nHOST_B: Hello")
    mocker.patch("main.parse_script", return_value=[("HOST_A", "Hi"), ("HOST_B", "Hello")])
    mocker.patch("main.generate_audio_for_lines", return_value=["/tmp/a.mp3"])
    mocker.patch("main.stitch_audio", return_value=True)
    mocker.patch("main.upload_to_drive", return_value=True)
    mocker.patch("main.generate_podcast_rss", return_value=True)

    entry = _make_entry()
    result = process_entry(
        entry, _default_show(), "Feed", "http://feed.url",
        _default_gen(), _default_audio(),
        MagicMock(), MagicMock(), MagicMock(), db,
    )

    assert result is True
    assert db.is_processed("show-1", "id-1")


# --- Partial failures ---

def test_process_entry_returns_false_if_upload_fails(db, mocker):
    """Returns False (and does not mark processed) if upload fails."""
    mocker.patch("main.fetch_article_text", return_value="x" * 200)
    mocker.patch("main.generate_script", return_value="HOST_A: Hi")
    mocker.patch("main.parse_script", return_value=[("HOST_A", "Hi")])
    mocker.patch("main.generate_audio_for_lines", return_value=["/tmp/a.mp3"])
    mocker.patch("main.stitch_audio", return_value=True)
    mocker.patch("main.upload_to_drive", return_value=False)

    entry = _make_entry()
    result = process_entry(
        entry, _default_show(), "Feed", "http://feed.url",
        _default_gen(), _default_audio(),
        MagicMock(), MagicMock(), MagicMock(), db,
    )

    assert result is False
    assert not db.is_processed("show-1", "id-1")


def test_process_entry_returns_false_if_script_generation_fails(db, mocker):
    """Returns False if script generation returns None."""
    mocker.patch("main.fetch_article_text", return_value="x" * 200)
    mocker.patch("main.generate_script", return_value=None)

    entry = _make_entry()
    result = process_entry(
        entry, _default_show(), "Feed", "http://feed.url",
        _default_gen(), _default_audio(),
        MagicMock(), MagicMock(), MagicMock(), db,
    )

    assert result is False
    assert not db.is_processed("show-1", "id-1")
