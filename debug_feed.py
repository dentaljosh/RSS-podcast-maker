import feedparser
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

for feed in config.get('feeds', []):
    url = feed.get('url')
    print(f"Parsing: {url}")
    parsed = feedparser.parse(url)
    print(f"Found {len(parsed.entries)} entries")
    if parsed.entries:
        entry = parsed.entries[0]
        print(f"First entry title: {entry.get('title')}")
        print(f"First entry link: {entry.get('link')}")
        print(f"First entry id: {entry.get('id')}")
