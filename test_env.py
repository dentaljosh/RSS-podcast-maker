import subprocess
import os
from pydub import AudioSegment

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        print("✅ ffmpeg is installed and available in PATH.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg NOT found. Please install it with 'brew install ffmpeg'.")
        return False

def check_dependencies():
    try:
        import anthropic
        import openai
        import feedparser
        import yaml
        import googleapiclient
        import dotenv
        print("✅ Python dependencies are correctly installed.")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

if __name__ == "__main__":
    print("--- Mac Environment Check ---")
    f = check_ffmpeg()
    d = check_dependencies()
    if f and d:
        print("\n🎉 Environment is ready for testing!")
    else:
        print("\n⚠️ Please fix the errors above before running.")
