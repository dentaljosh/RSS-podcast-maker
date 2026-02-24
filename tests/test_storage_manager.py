import pytest
from unittest.mock import MagicMock
from storage_manager import generate_podcast_rss

def test_generate_podcast_rss_xml_structure(mocker):
    # Mock Google Drive service
    mock_drive = MagicMock()
    
    # Mock the file listing response
    mock_files = {
        'files': [
            {
                'id': 'file123',
                'name': 'Episode 1.mp3',
                'createdTime': '2024-02-23T22:00:00.000Z',
                'size': '1234567'
            }
        ]
    }
    mock_drive.files().list().execute.side_effect = [mock_files, {'files': []}] # 1. list mp3s, 2. check for xml
    mock_drive.files().create().execute.return_value = {'id': 'new_xml_id'}
    
    config = {
        'google_drive': {'folder_id': 'folder_abc'},
        'podcast_info': {
            'title': 'Test Podcast',
            'description': 'Test Desc',
            'rss_filename': 'test.xml'
        }
    }
    
    # Mock environment and Gist update to avoid network
    mocker.patch('os.environ.get', return_value=None)
    
    success = generate_podcast_rss(mock_drive, config)
    
    assert success is True
    # Verify drive calls were made
    assert mock_drive.files().list.called
    assert mock_drive.files().create.called

def test_generate_podcast_rss_no_folder():
    config = {'google_drive': {}}
    success = generate_podcast_rss(None, config)
    assert success is False
