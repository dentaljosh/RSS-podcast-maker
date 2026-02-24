import os
import io
import time
import logging
from datetime import datetime
from email.utils import format_datetime
from github import Github, InputFileContent
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

def get_drive_service():
    """Initializes and returns the Google Drive API service with OAuth2."""
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secrets.json'):
                raise FileNotFoundError("client_secrets.json not found. See README.")
            flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def upload_to_drive(drive_service, filename, folder_id, title, max_retries=3):
    """Uploads an MP3 to Google Drive and makes it public-readable."""
    for attempt in range(max_retries):
        try:
            file_metadata = {'name': title, 'parents': [folder_id]}
            media = MediaFileUpload(filename, mimetype='audio/mpeg', resumable=True)
            file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            drive_service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            logging.info(f"Successfully uploaded: {title} ({file.get('id')})")
            return True
        except Exception as e:
            logging.warning(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return False

def update_gist(token, gist_id, filename, content):
    """Updates a GitHub Gist with the provided RSS content."""
    try:
        g = Github(token)
        gist = g.get_gist(gist_id)
        gist.edit(
            description="RSS Podcast Feed",
            files={filename: InputFileContent(content)}
        )
        return True
    except Exception as e:
        logging.error(f"Failed to update GitHub Gist: {e}")
        return False

def generate_podcast_rss(drive_service, show_config):
    """Generates the RSS feed XML and syncs it to Drive and GitHub Gists for a specific show."""
    try:
        folder_id = show_config['google_drive']['folder_id']
        podcast_info = show_config.get('podcast_info', {})
        rss_title = podcast_info.get('title', 'My RSS Podcast Feed')
        rss_description = podcast_info.get('description', 'AI-generated summaries.')
        rss_filename = podcast_info.get('rss_filename', 'podcast.xml')
        
        logging.info(f"Generating updated {rss_filename} RSS feed...")
        
        query = f"'{folder_id}' in parents and mimeType = 'audio/mpeg' and trashed = false"
        results = drive_service.files().list(q=query, fields='files(id, name, createdTime, size)', orderBy='createdTime desc').execute()
        files = results.get('files', [])

        rss = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
            '  <channel>',
            f'    <title>{rss_title}</title>',
            f'    <description>{rss_description}</description>',
            f'    <link>https://drive.google.com/drive/folders/{folder_id}</link>',
            f'    <language>en-us</language>',
            '    <itunes:author>RSS Podcast Maker</itunes:author>',
            f'    <itunes:summary>{rss_description}</itunes:summary>',
            '    <itunes:owner>',
            '      <itunes:name>RSS Podcast Maker</itunes:name>',
            f'      <itunes:email>{podcast_info.get("email", "podcast@yourdomain.com")}</itunes:email>',
            '    </itunes:owner>',
            '    <itunes:explicit>no</itunes:explicit>',
            '    <itunes:block>Yes</itunes:block>'
        ]
        
        for f in files:
            file_id = f['id']
            enclosure_url = f"https://docs.google.com/uc?export=download&id={file_id}"
            dt = datetime.strptime(f['createdTime'], '%Y-%m-%dT%H:%M:%S.%fZ')
            pub_date = format_datetime(dt)
            
            rss.extend([
                '    <item>',
                f'      <title><![CDATA[{f["name"]}]]></title>',
                f'      <enclosure url="{enclosure_url}" length="{f.get("size", 0)}" type="audio/mpeg"/>',
                f'      <guid isPermaLink="false">{file_id}</guid>',
                f'      <pubDate>{pub_date}</pubDate>',
                '    </item>'
            ])
            
        rss.extend(['  </channel>', '</rss>'])
        content = "\n".join(rss)
        
        xml_query = f"'{folder_id}' in parents and name = '{rss_filename}' and trashed = false"
        xml_results = drive_service.files().list(q=xml_query, fields='files(id)').execute()
        xml_files = xml_results.get('files', [])
        
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='application/rss+xml', resumable=True)
        
        if xml_files:
            drive_service.files().update(fileId=xml_files[0]['id'], media_body=media).execute()
        else:
            file_metadata = {'name': rss_filename, 'parents': [folder_id]}
            new_xml = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            drive_service.permissions().create(fileId=new_xml.get('id'), body={'type': 'anyone', 'role': 'reader'}).execute()
            
        logging.info(f"Successfully updated {rss_filename} on Google Drive")
        
        github_token = os.environ.get("GITHUB_TOKEN")
        gist_id = show_config.get('github', {}).get('gist_id')
        if github_token and gist_id:
            if update_gist(github_token, gist_id, rss_filename, content):
                logging.info(f"Successfully updated GitHub Gist for {rss_filename}.")
        
        return True
    except Exception as e:
        logging.error(f"Failed to generate podcast RSS: {e}")
        return False
