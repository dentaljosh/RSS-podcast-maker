import pytest
from rss_handler import safe_filename, fetch_article_text

def test_safe_filename_basic():
    assert safe_filename("Normal Title") == "Normal Title"
    assert safe_filename("Title with / Special @ Characters!") == "Title with  Special  Characters"

def test_safe_filename_trailing_spaces():
    assert safe_filename("Title with space at end ") == "Title with space at end"

def test_safe_filename_alphanumeric():
    assert safe_filename("Episode 123 (Testing)") == "Episode 123 Testing" # Note: parens are stripped in current impl

def test_safe_filename_dashes_and_dots():
    assert safe_filename("My-Cool_Episode.v1") == "My-Cool_Episode.v1"
