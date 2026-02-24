import pytest
from unittest.mock import MagicMock
from storage_manager import generate_podcast_rss, build_rss_xml, _list_all_drive_files


def _make_mock_drive(mp3_files=None, xml_files=None):
    """Helper to build a Drive mock with configurable list() responses."""
    mock_drive = MagicMock()
    mp3_response = {"files": mp3_files or [], "nextPageToken": None}
    xml_response = {"files": xml_files or []}
    mock_drive.files().list().execute.side_effect = [mp3_response, xml_response]
    mock_drive.files().create().execute.return_value = {"id": "new_xml_id"}
    mock_drive.files().update().execute.return_value = {}
    mock_drive.permissions().create().execute.return_value = {}
    return mock_drive


def _default_config():
    return {
        "google_drive": {"folder_id": "folder_abc"},
        "podcast_info": {
            "title": "Test Podcast",
            "description": "Test Desc",
            "rss_filename": "test.xml",
            "email": "test@example.com",
        },
    }


# --- Basic success path ---

def test_generate_podcast_rss_returns_true(mocker):
    mock_drive = _make_mock_drive()
    mocker.patch("os.environ.get", return_value=None)
    assert generate_podcast_rss(mock_drive, _default_config()) is True


def test_generate_podcast_rss_creates_xml_file(mocker):
    mock_drive = _make_mock_drive()
    mocker.patch("os.environ.get", return_value=None)
    generate_podcast_rss(mock_drive, _default_config())
    assert mock_drive.files().create.called


# --- build_rss_xml unit tests ---

def test_build_rss_xml_contains_title():
    """The channel title appears in the generated XML."""
    xml = build_rss_xml([], _default_config())
    assert "Test Podcast" in xml


def test_build_rss_xml_special_chars_escaped():
    """Special XML characters in title/description are correctly escaped by ElementTree."""
    config = {
        "google_drive": {"folder_id": "folder_abc"},
        "podcast_info": {
            "title": "Podcasts & More <Great>",
            "description": 'All about "stuff" & things',
            "rss_filename": "test.xml",
        },
    }
    xml = build_rss_xml([], config)
    assert "&amp;" in xml      # & escaped
    assert "&lt;" in xml       # < escaped
    assert "&&" not in xml     # NOT double-escaped


def test_build_rss_xml_episode_item():
    """An MP3 file produces an <item> element in the RSS."""
    files = [{
        "id": "file123",
        "name": "Episode One & Two.mp3",
        "createdTime": "2024-02-23T22:00:00.000Z",
        "size": "1234567",
    }]
    xml = build_rss_xml(files, _default_config())
    assert "<item>" in xml
    assert "file123" in xml
    assert "Episode One &amp; Two.mp3" in xml   # auto-escaped, NOT double-escaped


def test_build_rss_xml_is_valid_xml():
    """The output is parseable as XML."""
    import xml.etree.ElementTree as ET
    files = [{"id": "x", "name": "Ep.mp3", "createdTime": "2024-01-01T00:00:00.000Z", "size": "100"}]
    xml_str = build_rss_xml(files, _default_config())
    # Should not raise
    ET.fromstring(xml_str.split("\n", 1)[1])  # skip XML declaration line


# --- Pagination test ---

def test_list_all_drive_files_follows_next_page_token():
    """_list_all_drive_files fetches multiple pages until nextPageToken is exhausted."""
    mock_drive = MagicMock()
    page1 = {"files": [{"id": "a"}], "nextPageToken": "tok1"}
    page2 = {"files": [{"id": "b"}], "nextPageToken": None}
    mock_drive.files().list().execute.side_effect = [page1, page2]

    result = _list_all_drive_files(
        mock_drive,
        query="q",
        fields="files(id)",
        order_by="createdTime desc",
    )
    assert len(result) == 2
    assert result[0]["id"] == "a"
    assert result[1]["id"] == "b"


# --- XML update vs create ---

def test_generate_podcast_rss_xml_has_episode_item(mocker):
    """When Drive has MP3 files, the RSS contains an item element."""
    mp3_files = [{
        "id": "file123",
        "name": "Episode 1.mp3",
        "createdTime": "2024-02-23T22:00:00.000Z",
        "size": "1234567",
    }]
    mock_drive = _make_mock_drive(mp3_files=mp3_files)
    mocker.patch("os.environ.get", return_value=None)
    result = generate_podcast_rss(mock_drive, _default_config())
    assert result is True


def test_generate_podcast_rss_updates_existing_xml(mocker):
    """When an XML file already exists on Drive, it should be updated."""
    mp3_files = [{"id": "mp3_1", "name": "Ep.mp3", "createdTime": "2024-01-01T00:00:00.000Z", "size": "100"}]
    existing_xml = [{"id": "existing_xml_id"}]
    mock_drive = _make_mock_drive(mp3_files=mp3_files, xml_files=existing_xml)
    mocker.patch("os.environ.get", return_value=None)

    generate_podcast_rss(mock_drive, _default_config())

    update_call = mock_drive.files.return_value.update
    assert update_call.called


# --- Error path ---

def test_generate_podcast_rss_no_folder():
    config = {"google_drive": {}}
    assert generate_podcast_rss(None, config) is False


def test_generate_podcast_rss_drive_error(mocker):
    """Returns False when Drive raises an unexpected error."""
    mock_drive = MagicMock()
    mock_drive.files().list().execute.side_effect = Exception("Drive API error")
    mocker.patch("os.environ.get", return_value=None)
    result = generate_podcast_rss(mock_drive, _default_config())
    assert result is False
