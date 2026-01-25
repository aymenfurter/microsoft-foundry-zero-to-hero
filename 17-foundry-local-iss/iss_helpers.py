"""
ISS Report Helper Functions

Fetches REAL ISS Daily Summary Reports from NASA's official blog.
Data available from March 2013 to July 29, 2024 (when the blog was discontinued).

Source: https://www.nasa.gov/blogs/stationreport/
"""

import json
import re
from datetime import datetime
from typing import Optional
import urllib.request
import urllib.error


# NASA ISS Daily Summary Report blog was active from March 2013 to July 29, 2024
DATA_START_DATE = "2013-03-01"
DATA_END_DATE = "2024-07-29"


def _build_nasa_url(date: str) -> str:
    """
    Build the NASA blog URL for a specific date.
    
    URL format: https://www.nasa.gov/blogs/stationreport/YYYY/MM/DD/iss-daily-summary-report-M-D-YYYY/
    Note: Month and day in the slug don't have leading zeros.
    """
    dt = datetime.strptime(date, "%Y-%m-%d")
    year = dt.year
    month = dt.month
    day = dt.day
    
    # URL uses zero-padded month/day in path but non-padded in slug
    url = f"https://www.nasa.gov/blogs/stationreport/{year}/{month:02d}/{day:02d}/iss-daily-summary-report-{month}-{day}-{year}/"
    return url


def _fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch content from a URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; ISS-Chatbot/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None
    except Exception:
        return None


def _parse_report_content(html: str) -> dict:
    """
    Parse the NASA blog HTML to extract report content.
    Returns a simplified dict with the key information.
    """
    content = {}
    
    # Extract title
    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if title_match:
        content['title'] = title_match.group(1).strip()
    
    # Clean up HTML to extract text
    text = html
    
    # Remove script and style tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
    text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
    
    # Convert some tags to text markers
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<h[1-6][^>]*>', '\n## ', text)
    text = re.sub(r'</h[1-6]>', '\n', text)
    text = re.sub(r'<li[^>]*>', '\n- ', text)
    
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up whitespace
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    text = text.strip()
    
    # Decode HTML entities
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&#8217;', "'")
    text = text.replace('&#8211;', '-')
    text = text.replace('&#8220;', '"')
    text = text.replace('&#8221;', '"')
    
    # Find the main report content - it typically starts after the title
    # and contains "Payloads:" or similar markers
    report_start = text.find('Payloads')
    if report_start == -1:
        report_start = text.find('ISS Daily Summary')
    if report_start == -1:
        report_start = 0
    
    # Find where the report ends (before footer content)
    report_end = text.find('More from ISS')
    if report_end == -1:
        report_end = text.find('Share on')
    if report_end == -1:
        report_end = len(text)
    
    report_text = text[report_start:report_end].strip()
    content['report_text'] = report_text
    
    # Try to extract sections
    sections = {}
    
    # Look for Payloads section
    payloads_match = re.search(r'Payloads?:?\s*(.*?)(?=Systems?:|Look Ahead|Today\'s|Completed|\n## |$)', report_text, re.DOTALL | re.IGNORECASE)
    if payloads_match:
        sections['payloads'] = payloads_match.group(1).strip()[:2500]
    
    # Look for Systems section
    systems_match = re.search(r'Systems?:?\s*(.*?)(?=Look Ahead|Today\'s|Completed|\n## |$)', report_text, re.DOTALL | re.IGNORECASE)
    if systems_match:
        sections['systems'] = systems_match.group(1).strip()[:1500]
    
    content['sections'] = sections
    
    return content


def get_report_by_date(date: str) -> str:
    """
    Fetch the ISS daily report for a specific date from NASA's blog.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2024-07-18")
              Data available from 2013-03-01 to 2024-07-29
    
    Returns:
        JSON string with the report data, or error if not found.
    """
    # Validate date format
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return json.dumps({
            "success": False,
            "error": f"Invalid date format: {date}. Use YYYY-MM-DD format."
        })
    
    # Check date range
    start_dt = datetime.strptime(DATA_START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(DATA_END_DATE, "%Y-%m-%d")
    
    if dt < start_dt or dt > end_dt:
        return json.dumps({
            "success": False,
            "error": f"Date {date} is outside available range.",
            "available_range": {
                "start": DATA_START_DATE,
                "end": DATA_END_DATE
            },
            "note": "NASA's ISS Daily Summary blog was active from March 2013 to July 29, 2024."
        })
    
    # Build URL and fetch
    url = _build_nasa_url(date)
    
    html = _fetch_url(url)
    
    if html is None:
        # Try without the trailing slash
        url_alt = url.rstrip('/')
        html = _fetch_url(url_alt)
    
    if html is None:
        return json.dumps({
            "success": False,
            "error": f"No report found for {date}. The report may not exist for this date (weekends/holidays often have no reports).",
            "url_attempted": url,
            "suggestion": "Try a nearby weekday date. Reports were typically published Monday-Friday."
        })
    
    # Parse the content
    content = _parse_report_content(html)
    
    return json.dumps({
        "success": True,
        "date": date,
        "day_of_week": dt.strftime("%A"),
        "source_url": url,
        "title": content.get('title', f"ISS Daily Summary Report - {date}"),
        "report_text": content.get('report_text', '')[:5000],  # Limit size for LLM context
        "sections": content.get('sections', {}),
        "note": "Real data from NASA's official ISS Daily Summary Report blog."
    })


# Map function names to actual functions
FUNCTION_MAP = {
    "get_report_by_date": get_report_by_date,
}


# Foundry Local uses a simpler tool format
FOUNDRY_LOCAL_TOOLS = [
    {
        "name": "get_report_by_date",
        "description": "Fetch the real ISS Daily Summary Report from NASA for a specific date. Data available from March 2013 to July 29, 2024. Use YYYY-MM-DD format.",
        "parameters": {
            "date": {"type": "string", "description": "Date in YYYY-MM-DD format (e.g., '2024-07-18')"}
        }
    }
]


def execute_function(name: str, arguments: dict) -> str:
    """Execute a function by name with the given arguments."""
    if name not in FUNCTION_MAP:
        return json.dumps({"error": f"Unknown function: {name}"})
    
    func = FUNCTION_MAP[name]
    return func(**arguments)


def parse_foundry_local_response(content: str) -> list:
    """
    Parse Foundry Local's function call response format.
    Foundry Local returns: functools[{...}] as text content.
    
    Returns list of dicts with 'name' and 'arguments' keys.
    """
    if not content:
        return []
    
    # Look for functools[...] pattern
    match = re.search(r'functools\[(.*)\]', content, re.DOTALL)
    if not match:
        return []
    
    try:
        # Parse the JSON array inside functools[...]
        tools_json = match.group(1)
        tools = json.loads(f"[{tools_json}]") if not tools_json.startswith('[') else json.loads(tools_json)
        
        # Normalize to list
        if isinstance(tools, dict):
            tools = [tools]
        
        return tools
    except json.JSONDecodeError:
        return []

