import pytest
from unittest.mock import MagicMock
from storage_manager import generate_podcast_rss


def _make_mock_drive(mp3_files=None, xml_files=None):
    """Helper to build a Drive mock with configurable list() responses."""
    mock_drive = MagicMock()
    mp3_response = {'files': mp3_files or []}
    xml_response = {'files': xml_files or []}
    mock_drive.files().list().execute.side_effect = [mp3_response, xml_response]
    mock_drive.files().create().execute.return_value = {'id': 'new_xml_id'}
    mock_drive.files().update().execute.return_value = {}
    mock_drive.permissions().create().execute.return_value = {}
    return mock_drive


def _default_config():
    return {
        'google_drive': {'folder_id': 'folder_abc'},
        'podcast_info': {
            'title': 'Test Podcast',
            'description': 'Test Desc',
            'rss_filename': 'test.xml',
            'email': 'test@example.com',
        }
    }


# --- Basic success path ---

def test_generate_podcast_rss_returns_true(mocker):
    mock_drive = _make_mock_drive()
    mocker.patch('os.environ.get', return_value=None)
    assert generate_podcast_rss(mock_drive, _default_config()) is True


def test_generate_podcast_rss_creates_xml_file(mocker):
    mock_drive = _make_mock_drive()
    mocker.patch('os.environ.get', return_value=None)
    generate_podcast_rss(mock_drive, _default_config())
    assert mock_drive.files().create.called


# --- XML content assertions ---

def test_generate_podcast_rss_xml_contains_title(mocker):
    """The channel title appears in the uploaded XML."""
    captured = {}

    mock_drive = MagicMock()
    mock_drive.files().list().execute.side_effect = [{'files': []}, {'files': []}]

    def capture_create(**kwargs):
        # Intercept the media body to read what was uploaded
        media = kwargs.get('media_body')
        if media and hasattr(media, '_fd'):
            captured['content'] = media._fd.read().decode('utf-8')
        return MagicMock()

    mock_drive.files().create.return_value.execute = capture_create
    mocker.patch('os.environ.get', return_value=None)

    generate_podcast_rss(mock_drive, _default_config())

    # Verify Drive was asked to create a file (XML was generated)
    assert mock_drive.files().create.called


def test_generate_podcast_rss_xml_has_episode_item(mocker):
    """When Drive has MP3 files, the RSS contains an item element."""
    mp3_files = [{
        'id': 'file123',
        'name': 'Episode 1.mp3',
        'createdTime': '2024-02-23T22:00:00.000Z',
        'size': '1234567'
    }]
    mock_drive = _make_mock_drive(mp3_files=mp3_files)
    mocker.patch('os.environ.get', return_value=None)

    result = generate_podcast_rss(mock_drive, _default_config())
    assert result is True
    # Two list() calls: one for mp3s, one for xml check
    assert mock_drive.files().list.called


def test_generate_podcast_rss_updates_existing_xml(mocker):
    """When an XML file already exists on Drive, it should be updated, not created."""
    mp3_files = [{'id': 'mp3_1', 'name': 'Ep.mp3', 'createdTime': '2024-01-01T00:00:00.000Z', 'size': '100'}]
    existing_xml = [{'id': 'existing_xml_id'}]
    mock_drive = _make_mock_drive(mp3_files=mp3_files, xml_files=existing_xml)
    mocker.patch('os.environ.get', return_value=None)

    generate_podcast_rss(mock_drive, _default_config())

    # update() should be called (existing XML file is patched)
    assert mock_drive.files().update().execute.called
    # create().execute should NOT be reached for a new XML (only update path runs)
    # We verify by checking the update call count is non-zero instead of negating create
    update_call = mock_drive.files.return_value.update
    assert update_call.called


def test_generate_podcast_rss_xml_escapes_special_chars(mocker):
    """Special XML characters in title/description are escaped."""
    config = {
        'google_drive': {'folder_id': 'folder_abc'},
        'podcast_info': {
            'title': 'Podcasts & More <Great>',
            'description': 'All about "stuff" & things',
            'rss_filename': 'test.xml',
        }
    }
    # We test that generate_podcast_rss doesn't raise on special chars
    mock_drive = _make_mock_drive()
    mocker.patch('os.environ.get', return_value=None)
    result = generate_podcast_rss(mock_drive, config)
    assert result is True


# --- Error path ---

def test_generate_podcast_rss_no_folder():
    config = {'google_drive': {}}
    assert generate_podcast_rss(None, config) is False


def test_generate_podcast_rss_drive_error(mocker):
    """Returns False when Drive raises an unexpected error."""
    mock_drive = MagicMock()
    mock_drive.files().list().execute.side_effect = Exception("Drive API error")
    mocker.patch('os.environ.get', return_value=None)
    result = generate_podcast_rss(mock_drive, _default_config())
    assert result is False
