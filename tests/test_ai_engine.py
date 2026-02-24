import pytest
from ai_engine import parse_script

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
    assert parsed[0] == ('HOST_A', 'Start')
    assert parsed[1] == ('HOST_B', 'End')

def test_parse_script_no_prefix():
    script_text = "Just some random text\nHOST_A: Valid line"
    parsed = parse_script(script_text)
    assert len(parsed) == 1
    assert parsed[0] == ('HOST_A', 'Valid line')
