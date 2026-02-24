"""Environment sanity check for RSS Podcast Maker.

Verifies that FFmpeg is installed and all Python dependencies are importable.

Run from the project root: python scripts/test_env.py
"""
import subprocess


def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        print("✅ ffmpeg is installed and available in PATH.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg NOT found. Please install it with 'brew install ffmpeg'.")
        return False


def check_dependencies() -> bool:
    try:
        import anthropic  # noqa: F401
        import openai  # noqa: F401
        import feedparser  # noqa: F401
        import yaml  # noqa: F401
        import googleapiclient  # noqa: F401
        import dotenv  # noqa: F401
        import httpx  # noqa: F401
        print("✅ Python dependencies are correctly installed.")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False


if __name__ == "__main__":
    print("--- Environment Check ---")
    f = check_ffmpeg()
    d = check_dependencies()
    if f and d:
        print("\n🎉 Environment is ready!")
    else:
        print("\n⚠️ Please fix the errors above before running.")
