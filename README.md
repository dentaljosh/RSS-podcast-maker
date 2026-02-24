# RSS Podcast Maker 🎙️🤖

Transform any RSS feed (like Substack) into a professional, two-host AI podcast. This tool uses Anthropic's Claude to write scripts and OpenAI's TTS to generate high-quality audio, then hosts the feed for you.

## ✨ Features
- **Two-Host Dialogue**: Generates argumentative, high-energy discussions between two AI hosts.
- **Intro & Metadata**: Automatically adds intros with episode details and embeds ID3 tags.
- **Drive Hosting**: Uploads MP3s to Google Drive using direct-download links.
- **GitHub Gist RSS**: Hosts your RSS feed on GitHub Gists for 100% reliable subscription in apps like Pocket Casts.
- **Modular Design**: Cleanly separated logic for RSS handling, AI generation, and storage.

## 📁 Directory Structure
- `main.py`: The central loop that orchestrates the entire process.
- `rss_handler.py`: Handles article extraction and sanitization.
- `ai_engine.py`: Manages script generation and audio stitching.
- `storage_manager.py`: Connects to Google Drive and GitHub Gists.

## 🚀 Setup

### 1. Requirements
- Python 3.10+
- **FFmpeg**: Required for audio processing. (Install via `brew install ffmpeg` on macOS or `apt install ffmpeg` on Linux).

### 2. Installation
```bash
git clone https://github.com/yourusername/RSS-podcast-maker.git
cd RSS-podcast-maker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. API Keys (.env)
Create a `.env` file in the root directory:
```env
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GITHUB_TOKEN=your_github_token_with_gist_scope
```

### 4. Configuration
Copy `config.example.yaml` to `config.yaml` and fill in your details:
- **Google Drive Folder ID**: Where your MP3s will live.
- **GitHub Gist ID**: A secret gist to host your feed.
- **Email**: Recommended to add an `email:` field under `podcast_info` for iTunes compliance.

### 5. Google Drive Authentication
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Drive API**.
3. Create **OAuth 2.0 Client ID** credentials (Desktop App).
4. Download the JSON and save it as `client_secrets.json` in the project root.

## 🛠️ Usage
Simply run:
```bash
python main.py
```

## � Testing
The project includes a lean testing suite using `pytest`. To run tests:
```bash
pytest
```
This verifies filename sanitization, script parsing, and RSS generation logic without needing API keys.

## �🤝 Contributing
Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## ⚖️ License
MIT License. See [LICENSE](LICENSE) for details.
