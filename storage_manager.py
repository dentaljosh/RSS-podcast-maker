import io
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from typing import List, Optional

from github import Github, InputFileContent
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

__all__ = ["get_drive_service", "upload_to_drive", "build_rss_xml", "generate_podcast_rss"]

logger = logging.getLogger(__name__)

_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ET.register_namespace("itunes", _ITUNES_NS)


def _it(tag: str) -> str:
    """Returns the Clark-notation itunes namespace tag."""
    return f"{{{_ITUNES_NS}}}{tag}"


def get_drive_service():
    """Initializes and returns the Google Drive API service with OAuth2."""
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("client_secrets.json"):
                raise FileNotFoundError("client_secrets.json not found. See README.")
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def upload_to_drive(
    drive_service,
    filename: str,
    folder_id: str,
    title: str,
    max_retries: int = 3,
) -> bool:
    """Uploads an MP3 to Google Drive and makes it public-readable."""
    for attempt in range(max_retries):
        try:
            file_metadata = {"name": title, "parents": [folder_id]}
            media = MediaFileUpload(filename, mimetype="audio/mpeg", resumable=True)
            file = drive_service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()
            drive_service.permissions().create(
                fileId=file.get("id"),
                body={"type": "anyone", "role": "reader"},
            ).execute()
            logging.info(f"Successfully uploaded: {title} ({file.get('id')})")
            return True
        except Exception as e:
            logging.warning(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return False


def update_gist(token: str, gist_id: str, filename: str, content: str) -> bool:
    """Updates a GitHub Gist with the provided RSS content."""
    try:
        g = Github(token)
        gist = g.get_gist(gist_id)
        gist.edit(
            description="RSS Podcast Feed",
            files={filename: InputFileContent(content)},
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update GitHub Gist: {e}")
        return False


def _list_all_drive_files(
    drive_service,
    query: str,
    fields: str,
    order_by: str,
) -> List[dict]:
    """
    Fetches all matching files from Google Drive, handling nextPageToken pagination.

    Args:
        drive_service: Authenticated Google Drive API service.
        query: Drive files.list() query string.
        fields: Fields to return per file.
        order_by: Sort order string.

    Returns:
        A flat list of file metadata dicts across all pages.
    """
    files = []
    page_token: Optional[str] = None
    while True:
        kwargs: dict = dict(q=query, fields=fields, orderBy=order_by, pageSize=100)
        if page_token:
            kwargs["pageToken"] = page_token
        resp = drive_service.files().list(**kwargs).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def build_rss_xml(files: list, show_config: dict) -> str:
    """
    Builds a podcast RSS 2.0 XML string from Drive file metadata.

    Uses xml.etree.ElementTree for correct automatic escaping — no manual
    escape() calls needed. Special characters in titles (& < > etc.) are
    handled transparently.

    Args:
        files: List of Drive file metadata dicts (keys: id, name, createdTime, size).
        show_config: Show config dict matching the config.yaml show entry structure.

    Returns:
        A valid RSS 2.0 XML string with iTunes namespace extensions.
    """
    folder_id = show_config["google_drive"]["folder_id"]
    podcast_info = show_config.get("podcast_info", {})
    rss_title = podcast_info.get("title", "My RSS Podcast Feed")
    rss_description = podcast_info.get("description", "AI-generated summaries.")
    email = podcast_info.get("email", "podcast@yourdomain.com")

    # Build the RSS element tree
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = rss_title
    ET.SubElement(channel, "description").text = rss_description
    ET.SubElement(channel, "link").text = (
        f"https://drive.google.com/drive/folders/{folder_id}"
    )
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, _it("author")).text = "RSS Podcast Maker"
    ET.SubElement(channel, _it("summary")).text = rss_description
    ET.SubElement(channel, _it("explicit")).text = "no"
    ET.SubElement(channel, _it("block")).text = "Yes"

    owner = ET.SubElement(channel, _it("owner"))
    ET.SubElement(owner, _it("name")).text = "RSS Podcast Maker"
    ET.SubElement(owner, _it("email")).text = email

    for f in files:
        file_id = f["id"]
        enclosure_url = f"https://docs.google.com/uc?export=download&id={file_id}"
        dt = datetime.strptime(f["createdTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
        pub_date = format_datetime(dt)
        episode_title = f["name"]

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = episode_title  # ElementTree auto-escapes
        ET.SubElement(item, "description").text = episode_title
        ET.SubElement(item, _it("summary")).text = episode_title
        ET.SubElement(item, "enclosure", attrib={
            "url": enclosure_url,
            "length": str(f.get("size", 0)),
            "type": "audio/mpeg",
        })
        ET.SubElement(item, "guid", attrib={"isPermaLink": "false"}).text = file_id
        ET.SubElement(item, "pubDate").text = pub_date

    # Pretty-print (Python 3.9+); no-op on older versions
    try:
        ET.indent(rss, space="  ")
    except AttributeError:
        pass

    xml_body = ET.tostring(rss, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}'


def generate_podcast_rss(drive_service, show_config: dict) -> bool:
    """
    Orchestrates RSS feed generation for a show: fetches Drive files,
    builds XML, uploads to Drive, and syncs to GitHub Gist.

    Args:
        drive_service: Authenticated Google Drive API service.
        show_config: Show config dict from config.yaml.

    Returns:
        True on success, False on failure.
    """
    try:
        folder_id = show_config["google_drive"]["folder_id"]
        podcast_info = show_config.get("podcast_info", {})
        rss_filename = podcast_info.get("rss_filename", "podcast.xml")

        logger.info(f"Generating updated {rss_filename} RSS feed...")

        # 1. Fetch all MP3 files (with pagination)
        mp3_query = (
            f"'{folder_id}' in parents and mimeType = 'audio/mpeg' and trashed = false"
        )
        files = _list_all_drive_files(
            drive_service,
            query=mp3_query,
            fields="files(id, name, createdTime, size)",
            order_by="createdTime desc",
        )

        # 2. Build RSS XML
        content = build_rss_xml(files, show_config)

        # 3. Upload XML to Drive (create or update)
        xml_query = (
            f"'{folder_id}' in parents and name = '{rss_filename}' and trashed = false"
        )
        xml_results = drive_service.files().list(
            q=xml_query, fields="files(id)"
        ).execute()
        xml_files = xml_results.get("files", [])

        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype="application/rss+xml",
            resumable=True,
        )

        if xml_files:
            drive_service.files().update(
                fileId=xml_files[0]["id"], media_body=media
            ).execute()
        else:
            file_metadata = {"name": rss_filename, "parents": [folder_id]}
            new_xml = drive_service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()
            drive_service.permissions().create(
                fileId=new_xml.get("id"),
                body={"type": "anyone", "role": "reader"},
            ).execute()

        logger.info(f"Successfully updated {rss_filename} on Google Drive")

        # 4. Sync to GitHub Gist
        github_token = os.environ.get("GITHUB_TOKEN")
        gist_id = show_config.get("github", {}).get("gist_id")
        if github_token and gist_id:
            if update_gist(github_token, gist_id, rss_filename, content):
                logger.info(f"Successfully updated GitHub Gist for {rss_filename}.")

        return True

    except Exception as e:
        logger.error(f"Failed to generate podcast RSS: {e}")
        return False
