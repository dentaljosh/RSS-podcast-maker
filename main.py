import os
import json
import logging
import yaml
import feedparser
import requests
from datetime import datetime
from tempfile import TemporaryDirectory
from dotenv import load_dotenv
import httpx
from anthropic import Anthropic
from openai import OpenAI

# Import modular components
from rss_handler import fetch_article_text, safe_filename
from ai_engine import generate_script, parse_script, generate_audio_for_lines, stitch_audio
from storage_manager import get_drive_service, upload_to_drive, generate_podcast_rss

from db_manager import DatabaseManager

# Setup logging
logging.basicConfig(
    filename='pipeline.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def load_config():
    """Loads configuration from config.yaml."""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    """Main orchestration loop for the RSS Podcast Maker."""
    load_dotenv()
    try:
        config = load_config()
    except Exception as e:
        logging.error(f"Failed to load config.yaml: {e}")
        return
        
    db = DatabaseManager()
    
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    if not anthropic_key or not openai_key:
        logging.warning("API keys not set in environment.")

    # Use verify=False to handle macOS SSL issues if needed
    http_client = httpx.Client(verify=False, timeout=120.0)
    anthropic_client = Anthropic(api_key=anthropic_key, http_client=http_client)
    openai_client = OpenAI(api_key=openai_key, http_client=http_client)
    
    try:
        drive_service = get_drive_service()
    except Exception as e:
        logging.error(f"Failed to initialize Google Drive client: {e}")
        return
    
    # Global audio/generation settings
    global_gen = config.get('generation', {})
    global_audio = config.get('audio', {})

    for show in config.get('shows', []):
        show_id = show.get('id')
        show_name = show.get('name')
        logging.info(f"--- Processing show: {show_name} (ID: {show_id}) ---")
        
        # Merge show-specific settings with globals
        show_gen = {**global_gen, **show.get('generation', {})}
        show_audio = {**global_audio, **show.get('audio', {})}

        for feed in show.get('feeds', []):
            url = feed.get('url')
            feed_name = feed.get('name')
            logging.info(f"Processing feed: {feed_name}")
            
            try:
                # Common headers to avoid being blocked
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
                parsed_feed = feedparser.parse(response.content)
            except Exception as e:
                logging.error(f"Failed to fetch feed {url}: {e}")
                continue
                
            processed_count = 0
            for entry in parsed_feed.entries:
                if processed_count >= 1: # Safety limit
                    break
                    
                item_id = entry.get('id', entry.get('link'))
                if not item_id or db.is_processed(show_id, item_id):
                    continue
                    
                logging.info(f"Processing new item: {entry.title}")
                try:
                    # 1. Fetch text
                    article_url = entry.get('link', url)
                    article_text = fetch_article_text(article_url)
                    if not article_text:
                        article_text = entry.get('summary', '')
                    
                    if not article_text or len(article_text.strip()) < 100:
                        logging.warning(f"Skipping {entry.title}: text too short.")
                        continue

                    # 2. Generate script
                    logging.info(f"Generating script...")
                    script = generate_script(
                        anthropic_client,
                        show_gen['anthropic_model'],
                        article_text,
                        show_gen.get('target_length_minutes', 5)
                    )
                    if not script: continue
                        
                    lines = parse_script(script)
                    if not lines: continue

                    # Add intro line
                    intro_text = f"Welcome to today's summary. We are discussing the article '{entry.title}' from {feed_name}."
                    lines.insert(0, ('HOST_A', intro_text))

                    # 3. Audio generation
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    safe_title = safe_filename(entry.title)
                    if len(safe_title) > 50: safe_title = safe_title[:47] + "..."
                    
                    safe_feed_name = safe_filename(feed_name)
                    final_mp3_name = f"{safe_feed_name} - {safe_title} - {date_str}.mp3"
                    
                    with TemporaryDirectory() as temp_dir:
                        audio_files = generate_audio_for_lines(
                            openai_client, lines,
                            show_audio['openai_tts_model'],
                            show_audio['host_a_voice'],
                            show_audio['host_b_voice'],
                            temp_dir
                        )
                        
                        if not audio_files: continue
                            
                        stitched_local_path = os.path.join(temp_dir, "final.mp3")
                        mp3_tags = {"title": safe_title, "artist": "RSS Podcast Maker", "album": safe_feed_name}
                        
                        if stitch_audio(audio_files, stitched_local_path, tags=mp3_tags):
                            # 4. Storage & Feed Update
                            if upload_to_drive(drive_service, stitched_local_path, show['google_drive']['folder_id'], final_mp3_name):
                                generate_podcast_rss(drive_service, show)
                            
                    # 5. Finalize
                    db.mark_processed(show_id, item_id, title=entry.title, feed_name=feed_name)
                    processed_count += 1
                    logging.info(f"Finished: {entry.title}")
                    
                except Exception as e:
                    logging.error(f"Error processing {entry.title}: {e}")

if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
