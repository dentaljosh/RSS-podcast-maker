"""Debug utility to inspect configured RSS feeds.

Reads config.yaml from the project root and prints metadata for the
first entry of each feed across all configured shows.

Run from the project root: python scripts/debug_feed.py
"""
import os
import feedparser
import yaml

config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

for show in config.get("shows", []):
    print(f"\n=== Show: {show.get('name')} ===")
    for feed in show.get("feeds", []):
        url = feed.get("url")
        print(f"Parsing: {url}")
        parsed = feedparser.parse(url)
        print(f"Found {len(parsed.entries)} entries")
        if parsed.entries:
            entry = parsed.entries[0]
            print(f"First entry title: {entry.get('title')}")
            print(f"First entry link:  {entry.get('link')}")
            print(f"First entry id:    {entry.get('id')}")
