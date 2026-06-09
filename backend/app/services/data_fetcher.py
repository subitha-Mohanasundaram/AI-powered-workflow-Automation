"""
Real Data Fetcher Service.

Fetches live data from real external sources based on workflow intent.

Supported sources (all free, no API key required unless noted):
  - weather     : Open-Meteo API (free, no key)
  - news        : GNews API (free tier, key optional)
  - github      : GitHub public API (no key, higher limits with key)
  - currency    : ExchangeRate-API (free tier)
  - custom_url  : Any HTTP endpoint the user specifies
  - leetcode    : Already handled by leetcode.py

Intent is detected from the raw_request text.
"""
import json
from datetime import UTC, datetime
from typing import Optional

import requests

from ..logging_config import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10


# ── Weather ───────────────────────────────────────────────────────────────────

# City name → (latitude, longitude) for common Indian + global cities
_CITY_COORDS = {
    "chennai": (13.08, 80.27), "mumbai": (19.07, 72.87), "delhi": (28.61, 77.23),
    "bangalore": (12.97, 77.59), "bengaluru": (12.97, 77.59), "hyderabad": (17.38, 78.47),
    "kolkata": (22.57, 88.36), "pune": (18.52, 73.85), "ahmedabad": (23.02, 72.57),
    "jaipur": (26.91, 75.79), "coimbatore": (11.01, 76.97), "kochi": (9.93, 76.26),
    "london": (51.50, -0.12), "new york": (40.71, -74.00), "tokyo": (35.68, 139.69),
    "paris": (48.85, 2.35), "sydney": (-33.86, 151.21), "dubai": (25.20, 55.27),
    "singapore": (1.35, 103.82), "berlin": (52.52, 13.40),
}

_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def _detect_city(text: str) -> str:
    """Extract city name from request text."""
    lower = text.lower()
    for city in _CITY_COORDS:
        if city in lower:
            return city
    # Try to extract word after "for" or "in"
    for keyword in [" for ", " in ", " of "]:
        idx = lower.find(keyword)
        if idx != -1:
            word = lower[idx + len(keyword):].split()[0].strip(".,?!")
            return word
    return "chennai"  # default


def fetch_weather(city: Optional[str] = None, request_text: str = "") -> dict:
    """Fetch real weather data from Open-Meteo (free, no API key)."""
    city = (city or _detect_city(request_text)).lower().strip()
    coords = _CITY_COORDS.get(city)

    if not coords:
        # Try geocoding via Open-Meteo geocoding API
        try:
            geo_resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "en", "format": "json"},
                timeout=_TIMEOUT,
            )
            geo_data = geo_resp.json().get("results", [])
            if geo_data:
                coords = (geo_data[0]["latitude"], geo_data[0]["longitude"])
                city = geo_data[0].get("name", city)
            else:
                return {"error": f"City '{city}' not found", "source": "open-meteo"}
        except Exception as exc:
            logger.error("Geocoding error | city=%s | error=%s", city, exc)
            return {"error": f"Could not locate city '{city}'", "source": "open-meteo"}

    lat, lon = coords
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": [
                    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
                    "precipitation", "weather_code", "wind_speed_10m", "wind_direction_10m",
                    "surface_pressure", "visibility",
                ],
                "daily": [
                    "weather_code", "temperature_2m_max", "temperature_2m_min",
                    "precipitation_sum", "wind_speed_10m_max", "sunrise", "sunset",
                ],
                "timezone": "auto",
                "forecast_days": 5,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current", {})
        daily = data.get("daily", {})
        wmo = current.get("weather_code", 0)
        condition = _WMO_CODES.get(wmo, "Unknown")

        # Build 5-day forecast
        forecast = []
        dates = daily.get("time", [])
        for i, date in enumerate(dates[:5]):
            forecast.append({
                "date": date,
                "condition": _WMO_CODES.get(daily.get("weather_code", [0])[i] if i < len(daily.get("weather_code", [])) else 0, "Unknown"),
                "max_temp": f"{daily.get('temperature_2m_max', [])[i] if i < len(daily.get('temperature_2m_max', [])) else '--'}°C",
                "min_temp": f"{daily.get('temperature_2m_min', [])[i] if i < len(daily.get('temperature_2m_min', [])) else '--'}°C",
                "rain_mm": daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum", [])) else 0,
                "sunrise": daily.get("sunrise", [])[i].split("T")[-1] if i < len(daily.get("sunrise", [])) else "--",
                "sunset": daily.get("sunset", [])[i].split("T")[-1] if i < len(daily.get("sunset", [])) else "--",
            })

        result = {
            "source": "open-meteo",
            "city": city.title(),
            "coordinates": {"lat": lat, "lon": lon},
            "fetched_at": datetime.now(UTC).isoformat(),
            "current": {
                "temperature": f"{current.get('temperature_2m', '--')}°C",
                "feels_like": f"{current.get('apparent_temperature', '--')}°C",
                "humidity": f"{current.get('relative_humidity_2m', '--')}%",
                "condition": condition,
                "wind_speed": f"{current.get('wind_speed_10m', '--')} km/h",
                "wind_direction": f"{current.get('wind_direction_10m', '--')}°",
                "precipitation": f"{current.get('precipitation', 0)} mm",
                "pressure": f"{current.get('surface_pressure', '--')} hPa",
            },
            "forecast_5day": forecast,
            "summary": (
                f"{city.title()} weather: {condition}, "
                f"{current.get('temperature_2m', '--')}°C "
                f"(feels like {current.get('apparent_temperature', '--')}°C), "
                f"humidity {current.get('relative_humidity_2m', '--')}%, "
                f"wind {current.get('wind_speed_10m', '--')} km/h"
            ),
        }
        logger.info("Weather fetched | city=%s | condition=%s", city.title(), condition)
        return result

    except Exception as exc:
        logger.error("Weather fetch error | city=%s | error=%s", city, exc)
        return {"error": str(exc), "source": "open-meteo", "city": city}


# ── News ──────────────────────────────────────────────────────────────────────

def fetch_news(topic: Optional[str] = None, request_text: str = "", api_key: str = "") -> dict:
    """Fetch top news headlines. Uses GNews API (free tier: 100 req/day)."""
    topic = topic or _extract_topic(request_text) or "technology"
    try:
        params = {
            "q": topic,
            "lang": "en",
            "max": 10,
            "sortby": "publishedAt",
        }
        if api_key:
            params["apikey"] = api_key

        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=_TIMEOUT)

        if resp.status_code == 403:
            # Fallback to RSS via a public news API
            return _fetch_news_fallback(topic)

        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])

        result = {
            "source": "gnews",
            "topic": topic,
            "fetched_at": datetime.now(UTC).isoformat(),
            "total_results": data.get("totalArticles", len(articles)),
            "articles": [
                {
                    "title": a.get("title", ""),
                    "description": a.get("description", ""),
                    "url": a.get("url", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "published_at": a.get("publishedAt", ""),
                }
                for a in articles[:10]
            ],
            "summary": f"Top {len(articles)} news articles about '{topic}'",
        }
        logger.info("News fetched | topic=%s | count=%d", topic, len(articles))
        return result

    except Exception as exc:
        logger.error("News fetch error | topic=%s | error=%s", topic, exc)
        return _fetch_news_fallback(topic)


def _fetch_news_fallback(topic: str) -> dict:
    """Fallback news via HackerNews API (always free, no key)."""
    try:
        resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=_TIMEOUT)
        story_ids = resp.json()[:10]
        articles = []
        for sid in story_ids[:5]:
            s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
            if s and s.get("title"):
                articles.append({
                    "title": s.get("title", ""),
                    "url": s.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                    "source": "Hacker News",
                    "score": s.get("score", 0),
                    "published_at": datetime.fromtimestamp(s.get("time", 0), tz=UTC).isoformat(),
                })
        return {
            "source": "hackernews",
            "topic": topic,
            "fetched_at": datetime.now(UTC).isoformat(),
            "articles": articles,
            "summary": f"Top {len(articles)} trending tech stories",
        }
    except Exception as exc:
        return {"error": str(exc), "source": "hackernews", "topic": topic}


def _extract_topic(text: str) -> str:
    """Extract news topic from request text."""
    lower = text.lower()
    topics = ["technology", "business", "sports", "health", "science", "finance",
              "politics", "entertainment", "india", "world", "ai", "startup"]
    for t in topics:
        if t in lower:
            return t
    for kw in [" about ", " on ", " for "]:
        idx = lower.find(kw)
        if idx != -1:
            return lower[idx + len(kw):].split()[0].strip(".,?!")
    return "technology"


# ── GitHub ────────────────────────────────────────────────────────────────────

def fetch_github(repo: Optional[str] = None, request_text: str = "", token: str = "") -> dict:
    """Fetch public GitHub repo stats."""
    repo = repo or _extract_github_repo(request_text)
    if not repo:
        return {"error": "No GitHub repo specified. Use format: owner/repo", "source": "github"}

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        # Get recent commits
        commits_resp = requests.get(
            f"https://api.github.com/repos/{repo}/commits",
            headers=headers, params={"per_page": 5}, timeout=_TIMEOUT
        )
        recent_commits = []
        if commits_resp.ok:
            for c in commits_resp.json()[:5]:
                recent_commits.append({
                    "message": c["commit"]["message"].split("\n")[0][:80],
                    "author": c["commit"]["author"]["name"],
                    "date": c["commit"]["author"]["date"],
                })

        result = {
            "source": "github",
            "repo": repo,
            "fetched_at": datetime.now(UTC).isoformat(),
            "stats": {
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "watchers": data.get("watchers_count", 0),
                "language": data.get("language", "Unknown"),
                "size_kb": data.get("size", 0),
                "default_branch": data.get("default_branch", "main"),
            },
            "description": data.get("description", ""),
            "recent_commits": recent_commits,
            "summary": (
                f"{repo}: {data.get('stargazers_count', 0)} stars, "
                f"{data.get('forks_count', 0)} forks, "
                f"{data.get('open_issues_count', 0)} open issues. "
                f"Language: {data.get('language', 'Unknown')}."
            ),
        }
        logger.info("GitHub fetched | repo=%s | stars=%d", repo, data.get("stargazers_count", 0))
        return result

    except Exception as exc:
        logger.error("GitHub fetch error | repo=%s | error=%s", repo, exc)
        return {"error": str(exc), "source": "github", "repo": repo}


def _extract_github_repo(text: str) -> Optional[str]:
    import re
    match = re.search(r"([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", text)
    return match.group(1) if match else None


# ── Currency / Exchange rates ─────────────────────────────────────────────────

def fetch_currency(base: str = "USD", request_text: str = "") -> dict:
    """Fetch live exchange rates from ExchangeRate-API (free, no key)."""
    base = _extract_currency(request_text) or base
    try:
        resp = requests.get(
            f"https://open.er-api.com/v6/latest/{base.upper()}",
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("rates", {})

        # Show most relevant currencies
        key_currencies = ["USD", "EUR", "GBP", "JPY", "INR", "AUD", "CAD", "SGD", "AED", "CNY"]
        filtered = {k: rates[k] for k in key_currencies if k in rates and k != base.upper()}

        result = {
            "source": "open.er-api.com",
            "base_currency": base.upper(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "rates": filtered,
            "all_rates_count": len(rates),
            "summary": (
                f"1 {base.upper()} = " +
                ", ".join(f"{v:.2f} {k}" for k, v in list(filtered.items())[:5])
            ),
        }
        logger.info("Currency fetched | base=%s", base.upper())
        return result

    except Exception as exc:
        logger.error("Currency fetch error | base=%s | error=%s", base, exc)
        return {"error": str(exc), "source": "exchange-rate", "base": base}


def _extract_currency(text: str) -> Optional[str]:
    import re
    currencies = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "SGD", "AED", "CNY"]
    upper = text.upper()
    for c in currencies:
        if c in upper:
            return c
    return None


# ── Custom URL ────────────────────────────────────────────────────────────────

def fetch_custom_url(url: str, headers: Optional[dict] = None, method: str = "GET",
                     body: Optional[dict] = None) -> dict:
    """Fetch data from any HTTP endpoint specified by the user."""
    try:
        h = {"Content-Type": "application/json", "User-Agent": "AI-Workflow-Bot/1.0"}
        if headers:
            h.update(headers)

        if method.upper() == "POST":
            resp = requests.post(url, json=body, headers=h, timeout=15)
        else:
            resp = requests.get(url, headers=h, timeout=15)

        resp.raise_for_status()

        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text[:2000]}

        result = {
            "source": "custom_url",
            "url": url,
            "method": method.upper(),
            "status_code": resp.status_code,
            "fetched_at": datetime.now(UTC).isoformat(),
            "data": data,
            "summary": f"Successfully fetched data from {url} (HTTP {resp.status_code})",
        }
        logger.info("Custom URL fetched | url=%s | status=%d", url, resp.status_code)
        return result

    except Exception as exc:
        logger.error("Custom URL fetch error | url=%s | error=%s", url, exc)
        return {"error": str(exc), "source": "custom_url", "url": url}


# ── Intent-based auto-fetch ───────────────────────────────────────────────────

_WEATHER_KW = {"weather", "temperature", "forecast", "rain", "humidity", "climate", "hot", "cold"}
_NEWS_KW = {"news", "headlines", "articles", "latest", "trending", "breaking"}
_GITHUB_KW = {"github", "repo", "repository", "commits", "stars", "open issues"}
_CURRENCY_KW = {"currency", "exchange rate", "forex", "usd", "eur", "inr", "gbp", "dollar", "rupee"}


def auto_fetch(request_text: str, user_context: Optional[dict] = None) -> dict:
    """
    Automatically detect what data to fetch based on the request text
    and fetch it from the appropriate real source.

    user_context can contain:
      - custom_api_url: URL to call
      - custom_api_headers: dict of headers
      - custom_api_key: API key to pass
      - city: override city for weather
      - base_currency: override for currency
      - github_repo: override for GitHub
      - news_topic: override for news
    """
    ctx = user_context or {}
    lower = request_text.lower()

    # Custom URL takes highest priority
    if ctx.get("custom_api_url"):
        headers = ctx.get("custom_api_headers", {})
        if ctx.get("custom_api_key"):
            headers["Authorization"] = f"Bearer {ctx['custom_api_key']}"
        return fetch_custom_url(
            ctx["custom_api_url"],
            headers=headers,
            method=ctx.get("custom_api_method", "GET"),
            body=ctx.get("custom_api_body"),
        )

    # Detect intent from keywords
    if any(kw in lower for kw in _WEATHER_KW):
        return fetch_weather(city=ctx.get("city"), request_text=request_text)

    if any(kw in lower for kw in _NEWS_KW):
        return fetch_news(
            topic=ctx.get("news_topic"),
            request_text=request_text,
            api_key=ctx.get("news_api_key", ""),
        )

    if any(kw in lower for kw in _GITHUB_KW):
        return fetch_github(
            repo=ctx.get("github_repo"),
            request_text=request_text,
            token=ctx.get("github_token", ""),
        )

    if any(kw in lower for kw in _CURRENCY_KW):
        return fetch_currency(
            base=ctx.get("base_currency", "USD"),
            request_text=request_text,
        )

    # Default — return structured placeholder for unknown sources
    return {
        "source": "simulated",
        "fetched_at": datetime.now(UTC).isoformat(),
        "records": 50,
        "data": [{"id": i, "value": round(1000 + i * 47.5, 2), "label": f"Item {i}"} for i in range(1, 6)],
        "summary": "Simulated data — connect a real data source via custom_api_url in your workflow config",
    }
