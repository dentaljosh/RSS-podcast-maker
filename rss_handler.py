import requests
import logging
from bs4 import BeautifulSoup

def fetch_article_text(url):
    """
    Fetches the full text of an article from a URL, stripping HTML tags and boilerplate.
    
    Args:
        url (str): The URL of the article.
        
    Returns:
        str: The cleaned text content, or None if the fetch fails.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator=' ')
        # Collapse whitespace
        text = ' '.join(text.split())
        return text
    except Exception as e:
        logging.error(f"Failed to fetch article text from {url}: {e}")
        return None

def safe_filename(name):
    """
    Sanitizes a string for use as a filename by removing illegal characters.
    
    Args:
        name (str): The original string (e.g., article title).
        
    Returns:
        str: A sanitized string safe for most filesystems.
    """
    keepcharacters = (' ', '.', '_', '-')
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()
