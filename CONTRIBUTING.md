# Contributing to RSS Podcast Maker

Thank you for your interest in contributing! This project aims to make it easy for anyone to create AI-generated podcasts from their favorite feeds.

## 🛠️ Development Setup

1. **Fork & Clone**: Fork the repository and clone it to your local machine.
2. **Environment**: Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **API Keys**: Ensure you have keys for Anthropic, OpenAI, and a GitHub Token.

## 📁 Project Structure

- `main.py`: The main orchestration script.
- `rss_handler.py`: Logic for fetching and parsing RSS feeds and article text.
- `ai_engine.py`: Script generation (Anthropic) and Audio generation/stitching (OpenAI, Pydub).
- `storage_manager.py`: Google Drive and GitHub Gist integration logic.
- `config.yaml`: Configuration for feeds, models, and folder IDs.

## 📝 Guidelines

### Pull Requests
- Follow PEP 8 style guidelines.
- Add docstrings to any new functions.
- Ensure your changes don't break the core orchestration loop.
- Test your changes with a sample RSS feed before submitting.

### Issues
- Use the GitHub issue tracker for bugs or feature requests.
- Provide a clear description and steps to reproduce any bugs.

## ⚖️ License
By contributing, you agree that your contributions will be licensed under the MIT License.
