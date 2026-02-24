import logging
import os
from datetime import datetime
from tempfile import TemporaryDirectory
from typing import Any, Optional

import feedparser
import httpx
import yaml
from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

from ai_engine import generate_audio_for_lines, generate_script, parse_script, stitch_audio
from db_manager import DatabaseManager
from rss_handler import fetch_article_text, safe_filename
from storage_manager import generate_podcast_rss, upload_to_drive


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configures file and console logging. Call only from the entry point."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured; avoid duplicate handlers
    logging.basicConfig(
        filename="pipeline.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    root.addHandler(console)


def load_config() -> dict:
    """Loads configuration from config.yaml."""
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def process_entry(
    entry: Any,
    show: dict,
    feed_name: str,
    feed_url: str,
    show_gen: dict,
    show_audio: dict,
    anthropic_client: Anthropic,
    openai_client: OpenAI,
    drive_service: Any,
    db: DatabaseManager,
) -> bool:
    """
    Processes a single feed entry end-to-end.

    Checks the database for duplicates, fetches article text, generates a
    podcast script and audio, uploads the MP3 to Drive, regenerates the RSS
    feed, and marks the item as processed.

    Args:
        entry: A feedparser entry object.
        show: The show configuration dict from config.yaml.
        feed_name: Human-readable name of the source feed.
        feed_url: URL of the source feed (fallback for article URL).
        show_gen: Merged generation settings (global + show overrides).
        show_audio: Merged audio settings (global + show overrides).
        anthropic_client: Authenticated Anthropic API client.
        openai_client: Authenticated OpenAI API client.
        drive_service: Authenticated Google Drive API service.
        db: DatabaseManager instance for processed-item tracking.

    Returns:
        True if the entry was successfully processed, False if skipped or failed.
    """
    show_id: Optional[str] = show.get("id")
    item_id: Optional[str] = entry.get("id", entry.get("link"))

    if not item_id or db.is_processed(show_id, item_id):
        return False

    logger.info(f"Processing new item: {entry.title}")
    try:
        # 1. Fetch article text
        article_url = entry.get("link", feed_url)
        article_text = fetch_article_text(article_url)
        if not article_text:
            article_text = entry.get("summary", "")

        if not article_text or len(article_text.strip()) < 100:
            logger.warning(f"Skipping {entry.title}: text too short.")
            return False

        # 2. Generate script
        logger.info("Generating script...")
        script = generate_script(
            anthropic_client,
            show_gen["anthropic_model"],
            article_text,
            show_gen.get("target_length_minutes", 5),
        )
        if not script:
            return False

        lines = parse_script(script)
        if not lines:
            return False

        # Prepend intro line
        intro_text = (
            f"Welcome to today's summary. We are discussing the article "
            f"'{entry.title}' from {feed_name}."
        )
        lines.insert(0, ("HOST_A", intro_text))

        # 3. Audio generation
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = safe_filename(entry.title)
        if len(safe_title) > 50:
            safe_title = safe_title[:47] + "..."

        safe_feed_name = safe_filename(feed_name)
        final_mp3_name = f"{safe_feed_name} - {safe_title} - {date_str}.mp3"

        with TemporaryDirectory() as temp_dir:
            audio_files = generate_audio_for_lines(
                openai_client,
                lines,
                show_audio["openai_tts_model"],
                show_audio["host_a_voice"],
                show_audio["host_b_voice"],
                temp_dir,
            )
            if not audio_files:
                return False

            stitched_local_path = os.path.join(temp_dir, "final.mp3")
            mp3_tags = {
                "title": safe_title,
                "artist": "RSS Podcast Maker",
                "album": safe_feed_name,
            }

            if not stitch_audio(audio_files, stitched_local_path, tags=mp3_tags):
                logger.error(f"Audio stitching failed for {entry.title}")
                return False

            # 4. Upload & regenerate feed
            folder_id = show["google_drive"]["folder_id"]
            if not upload_to_drive(
                drive_service, stitched_local_path, folder_id, final_mp3_name
            ):
                logger.error(f"Upload failed for {entry.title}")
                return False

            generate_podcast_rss(drive_service, show)

        # 5. Persist — only reached on full success
        db.mark_processed(show_id, item_id, title=entry.title, feed_name=feed_name)
        logger.info(f"Finished: {entry.title}")
        return True

    except Exception as e:
        logger.error(f"Error processing {entry.title}: {e}")
        return False


def main() -> None:
    """Main orchestration loop for the RSS Podcast Maker."""
    load_dotenv()
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")
        return

    db = DatabaseManager()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not anthropic_key or not openai_key:
        logger.error("ANTHROPIC_API_KEY and OPENAI_API_KEY must both be set. Aborting.")
        return

    # Use explicit httpx clients so we can close them and avoid connection-pool leaks.
    anthropic_http = httpx.Client(timeout=120.0)
    openai_http = httpx.Client(timeout=120.0)
    try:
        anthropic_client = Anthropic(api_key=anthropic_key, http_client=anthropic_http)
        openai_client = OpenAI(api_key=openai_key, http_client=openai_http)

        try:
            drive_service = get_drive_service()
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive client: {e}")
            return

        global_gen = config.get("generation", {})
        global_audio = config.get("audio", {})
        global_processing = config.get("processing", {})
        max_items: int = global_processing.get("max_items_per_feed", 1)

        for show in config.get("shows", []):
            show_name = show.get("name")
            show_id = show.get("id")
            logger.info(f"--- Processing show: {show_name} (ID: {show_id}) ---")

            show_gen = {**global_gen, **show.get("generation", {})}
            show_audio = {**global_audio, **show.get("audio", {})}

            for feed in show.get("feeds", []):
                url = feed.get("url")
                feed_name = feed.get("name")
                logger.info(f"Processing feed: {feed_name}")

                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    response = httpx.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    parsed_feed = feedparser.parse(response.content)
                except Exception as e:
                    logger.error(f"Failed to fetch feed {url}: {e}")
                    continue

                processed_count = 0
                for entry in parsed_feed.entries:
                    if processed_count >= max_items:
                        break
                    if process_entry(
                        entry, show, feed_name, url,
                        show_gen, show_audio,
                        anthropic_client, openai_client,
                        drive_service, db,
                    ):
                        processed_count += 1
    finally:
        anthropic_http.close()
        openai_http.close()


if __name__ == "__main__":
    setup_logging()
    main()
