"""
Utility functions for web-related operations used by web search agents.
"""

import requests
from bs4 import BeautifulSoup


def fetch_url_content(url: str) -> str:
    """
    Fetch and parse content from a URL.

    Args:
        url: The URL to fetch content from

    Returns:
        str: The cleaned text content from the URL, limited to 8000 characters,
             or an error message if fetching fails
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Parse HTML content
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text content
        text = soup.get_text()

        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        return text[:8000]  # Limit to first 8k characters

    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"
