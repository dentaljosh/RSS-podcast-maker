import pytest
import time
from unittest.mock import MagicMock, patch, call
from ai_engine import generate_script, generate_audio_for_lines, parse_script, _with_retry


# --- parse_script tests (existing) ---

def test_parse_script_basic():
    script_text = "HOST_A: Hello\nHOST_B: Hi there"
    parsed = parse_script(script_text)
    assert len(parsed) == 2
    assert parsed[0] == ('HOST_A', 'Hello')
    assert parsed[1] == ('HOST_B', 'Hi there')

def test_parse_script_with_markdown():
    script_text = "**HOST_A:** Bold intro\n**HOST_B:** Bold response"
    parsed = parse_script(script_text)
    assert len(parsed) == 2
    assert parsed[0] == ('HOST_A', 'Bold intro')
    assert parsed[1] == ('HOST_B', 'Bold response')

def test_parse_script_empty_lines():
    script_text = "\nHOST_A: Start\n\nHOST_B: End\n"
    parsed = parse_script(script_text)
    assert len(parsed) == 2

def test_parse_script_no_prefix():
    script_text = "Just some random text\nHOST_A: Valid line"
    parsed = parse_script(script_text)
    assert len(parsed) == 1
    assert parsed[0] == ('HOST_A', 'Valid line')


# --- _with_retry tests ---

def test_with_retry_succeeds_on_first_try():
    fn = MagicMock(return_value="ok")
    result = _with_retry(fn, "test")
    assert result == "ok"
    assert fn.call_count == 1


def test_with_retry_succeeds_after_transient_failure(mocker):
    mocker.patch("ai_engine.time.sleep")  # don't actually sleep
    fn = MagicMock(side_effect=[RuntimeError("transient"), "ok"])
    result = _with_retry(fn, "test")
    assert result == "ok"
    assert fn.call_count == 2


def test_with_retry_raises_after_max_attempts(mocker):
    mocker.patch("ai_engine.time.sleep")
    fn = MagicMock(side_effect=RuntimeError("always fails"))
    with pytest.raises(RuntimeError, match="always fails"):
        _with_retry(fn, "test")
    assert fn.call_count == 3  # _MAX_RETRIES


def test_with_retry_uses_exponential_backoff(mocker):
    mock_sleep = mocker.patch("ai_engine.time.sleep")
    fn = MagicMock(side_effect=[RuntimeError(), RuntimeError(), RuntimeError()])
    with pytest.raises(RuntimeError):
        _with_retry(fn, "test")
    # Should have slept: 5s then 10s (not after the final failure)
    assert mock_sleep.call_count == 2
    delays = [c.args[0] for c in mock_sleep.call_args_list]
    assert delays[1] == delays[0] * 2  # exponential


# --- generate_script tests ---

def test_generate_script_success(mocker):
    mocker.patch("ai_engine.time.sleep")
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="HOST_A: Hello")]
    result = generate_script(mock_client, "claude-3", "article text", 5)
    assert result == "HOST_A: Hello"


def test_generate_script_returns_none_on_exhausted_retries(mocker):
    mocker.patch("ai_engine.time.sleep")
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("API down")
    result = generate_script(mock_client, "claude-3", "article text", 5)
    assert result is None
    assert mock_client.messages.create.call_count == 3  # retried 3x


# --- generate_audio_for_lines tests ---

def test_generate_audio_for_lines_success(mocker, tmp_path):
    mocker.patch("ai_engine.time.sleep")
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value.stream_to_file = MagicMock()

    lines = [("HOST_A", "Hello world"), ("HOST_B", "Hi there")]
    result = generate_audio_for_lines(mock_client, lines, "tts-1", "alloy", "echo", str(tmp_path))

    assert len(result) == 2
    assert mock_client.audio.speech.create.call_count == 2


def test_generate_audio_skips_empty_text(mocker, tmp_path):
    mocker.patch("ai_engine.time.sleep")
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value.stream_to_file = MagicMock()

    lines = [("HOST_A", ""), ("HOST_B", "Valid line")]
    result = generate_audio_for_lines(mock_client, lines, "tts-1", "alloy", "echo", str(tmp_path))

    assert len(result) == 1
    assert mock_client.audio.speech.create.call_count == 1


def test_generate_audio_raises_after_retries_exhausted(mocker, tmp_path):
    mocker.patch("ai_engine.time.sleep")
    mock_client = MagicMock()
    mock_client.audio.speech.create.side_effect = RuntimeError("TTS unavailable")

    lines = [("HOST_A", "Hello")]
    with pytest.raises(RuntimeError, match="TTS unavailable"):
        generate_audio_for_lines(mock_client, lines, "tts-1", "alloy", "echo", str(tmp_path))

    # Should have retried 3x
    assert mock_client.audio.speech.create.call_count == 3
