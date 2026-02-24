import functools
import logging
import os
import time
from typing import Callable, List, Optional, Tuple

from pydub import AudioSegment

__all__ = ["generate_script", "parse_script", "generate_audio_for_lines", "stitch_audio"]

logger = logging.getLogger(__name__)

# Max retries and base delay (seconds) for AI API calls
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5  # doubles each attempt: 5s, 10s, 20s


def _with_retry(fn: Callable, label: str):
    """
    Calls fn() with exponential backoff on failure.

    Args:
        fn: Zero-argument callable to execute.
        label: Description for log messages.

    Returns:
        The return value of fn() on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"{label} failed (attempt {attempt + 1}/{_MAX_RETRIES}): {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"{label} failed after {_MAX_RETRIES} attempts: {e}")
    raise last_exc  # type: ignore[misc]


def generate_script(
    anthropic_client,
    model: str,
    article_text: str,
    target_length_minutes: int,
) -> Optional[str]:
    """
    Generates a conversational podcast script using Anthropic's Claude.

    Retries up to 3 times with exponential backoff on transient API errors.

    Args:
        anthropic_client: The Anthropic API client.
        model: The model ID to use.
        article_text: The source text to summarize.
        target_length_minutes: Desired podcast length.

    Returns:
        The generated script text, or None if all retries fail.
    """
    system_prompt = (
        "You are writing a conversational podcast script for two hosts based on the provided article. "
        "Host A is the explainer — synthesizes and contextualizes from the article. "
        "Host B is the skeptic/questioner — pushes back, asks clarifying questions, highlights tension. "
        "The script should NOT read the article aloud. It should discuss, argue, and synthesize. "
        "Quotes from the original should be paraphrased unless a short exact quote meaningfully adds to the conversation. "
        "Lines MUST be prefixed strictly with 'HOST_A:' or 'HOST_B:'. Do not include sound effects or other staging instructions. "
        f"The target length for this podcast is approximately {target_length_minutes} minutes, so aim for a proportional word count (around {target_length_minutes * 150} words)."
    )

    def _call():
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Here is the article text:\n\n{article_text[:20000]}"}
            ]
        )
        return response.content[0].text

    try:
        return _with_retry(_call, "generate_script")
    except Exception:
        return None


def parse_script(script_text: str) -> List[Tuple[str, str]]:
    """
    Parses the raw script text into a list of (host, dialogue) pairs.
    """
    lines = script_text.split("\n")
    parsed: List[Tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("HOST_A:"):
            parsed.append(("HOST_A", line[len("HOST_A:"):].strip()))
        elif line.startswith("HOST_B:"):
            parsed.append(("HOST_B", line[len("HOST_B:"):].strip()))
        elif line.startswith("**HOST_A:**"):
            parsed.append(("HOST_A", line[len("**HOST_A:**"):].strip()))
        elif line.startswith("**HOST_B:**"):
            parsed.append(("HOST_B", line[len("**HOST_B:**"):].strip()))
    return parsed


def generate_audio_for_lines(
    openai_client,
    lines: List[Tuple[str, str]],
    model: str,
    host_a_voice: str,
    host_b_voice: str,
    temp_dir: str,
) -> List[str]:
    """
    Generates audio files for each line of dialogue using OpenAI's TTS.

    Each line is retried up to 3 times with exponential backoff. If a line
    still fails after all retries, the exception is re-raised to abort the
    entire episode.
    """
    audio_files: List[str] = []
    for idx, (host, text) in enumerate(lines):
        if not text:
            continue
        voice = host_a_voice if host == "HOST_A" else host_b_voice
        filename = os.path.join(temp_dir, f"{idx:04d}_{host}.mp3")

        def _tts_call(fn: str, v: str, t: str) -> None:
            response = openai_client.audio.speech.create(model=model, voice=v, input=t)
            response.stream_to_file(fn)

        # functools.partial binds the current loop values, avoiding late-binding closure bugs
        _with_retry(functools.partial(_tts_call, filename, voice, text), f"generate_audio line {idx}")
        audio_files.append(filename)

    return audio_files


def stitch_audio(
    audio_files: List[str],
    output_filename: str,
    tags: Optional[dict] = None,
) -> bool:
    """
    Merges multiple audio files and exports with ID3 metadata.
    """
    try:
        combined = AudioSegment.empty()
        for file in audio_files:
            segment = AudioSegment.from_mp3(file)
            combined += segment

        export_kwargs: dict = {"format": "mp3", "bitrate": "64k"}
        if tags:
            export_kwargs["tags"] = tags

        combined.export(output_filename, **export_kwargs)
        return True
    except Exception as e:
        logger.error(f"Failed to stitch audio: {e}")
        return False
