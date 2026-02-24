import pytest
import os
from db_manager import DatabaseManager

@pytest.fixture
def db():
    test_db = 'test_podcast_maker.db'
    if os.path.exists(test_db):
        os.remove(test_db)
    manager = DatabaseManager(db_path=test_db)
    yield manager
    if os.path.exists(test_db):
        os.remove(test_db)

def test_db_init(db):
    assert os.path.exists(db.db_path)

def test_mark_processed(db):
    show_id = "test-show"
    article_id = "article-1"
    
    assert not db.is_processed(show_id, article_id)
    assert db.mark_processed(show_id, article_id, title="Test", feed_name="Feed")
    assert db.is_processed(show_id, article_id)

def test_multi_show_isolation(db):
    show_a = "show-a"
    show_b = "show-b"
    article_id = "shared-article"
    
    db.mark_processed(show_a, article_id)
    assert db.is_processed(show_a, article_id)
    assert not db.is_processed(show_b, article_id)
    
    db.mark_processed(show_b, article_id)
    assert db.is_processed(show_b, article_id)

def test_get_processed_count(db):
    db.mark_processed("show-1", "a1")
    db.mark_processed("show-1", "a2")
    db.mark_processed("show-2", "b1")
    
    assert db.get_processed_count() == 3
    assert db.get_processed_count("show-1") == 2
    assert db.get_processed_count("show-2") == 1
