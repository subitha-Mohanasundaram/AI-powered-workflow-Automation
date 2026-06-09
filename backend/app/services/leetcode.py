"""
LeetCode Data Service.

Fetches real public profile data from LeetCode's GraphQL API.
No authentication required — only works with public profiles.

Data fetched per student:
  - Total solved (Easy / Medium / Hard)
  - Topic/tag breakdown (Arrays, Trees, DP, etc.)
  - Recent accepted submissions (last 20)
  - Contest rating and ranking
  - Global ranking
"""
import time
from datetime import UTC, datetime, timedelta
from typing import Optional

import requests

from ..logging_config import get_logger

logger = get_logger(__name__)

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# ── GraphQL queries ───────────────────────────────────────────────────────────

_PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      realName
      ranking
      userAvatar
      aboutMe
      school
      countryName
    }
    submitStats {
      acSubmissionNum {
        difficulty
        count
        submissions
      }
    }
    tagProblemCounts {
      advanced  { tagName tagSlug problemsSolved }
      intermediate { tagName tagSlug problemsSolved }
      fundamental  { tagName tagSlug problemsSolved }
    }
    badges { name icon }
    activeBadge { name }
  }
  recentAcSubmissionList(username: $username, limit: 20) {
    id
    title
    titleSlug
    timestamp
  }
  userContestRanking(username: $username) {
    attendedContestsCount
    rating
    globalRanking
    totalParticipants
    topPercentage
  }
}
"""


# ── Simple in-memory cache (TTL = 10 minutes) ─────────────────────────────────
_cache: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 600


def _cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL_SECONDS:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict) -> None:
    _cache[key] = {"ts": time.time(), "data": data}


# ── Core fetch function ───────────────────────────────────────────────────────

def fetch_student_stats(username: str) -> dict:
    """
    Fetch complete LeetCode stats for a username.
    Returns a structured dict. On error, returns an error dict (never raises).
    Results are cached for 10 minutes to avoid hammering LeetCode.
    """
    cached = _cache_get(username)
    if cached:
        logger.debug("Cache hit | username=%s", username)
        return cached

    logger.info("Fetching LeetCode stats | username=%s", username)
    try:
        resp = requests.post(
            LEETCODE_GRAPHQL_URL,
            json={"query": _PROFILE_QUERY, "variables": {"username": username}},
            headers=_HEADERS,
            timeout=12,
        )
        resp.raise_for_status()
        raw = resp.json()

        if "errors" in raw:
            err = raw["errors"][0].get("message", "Unknown error")
            logger.warning("LeetCode API error | username=%s | error=%s", username, err)
            return {"username": username, "error": err, "found": False}

        user_data = raw.get("data", {}).get("matchedUser")
        if not user_data:
            logger.warning("LeetCode user not found | username=%s", username)
            return {"username": username, "error": "User not found on LeetCode", "found": False}

        result = _parse_user_data(
            username,
            user_data,
            raw["data"].get("recentAcSubmissionList", []),
            raw["data"].get("userContestRanking"),
        )
        _cache_set(username, result)
        logger.info(
            "LeetCode stats fetched | username=%s | total_solved=%d",
            username,
            result["solved"]["total"],
        )
        return result

    except requests.exceptions.Timeout:
        logger.error("LeetCode API timeout | username=%s", username)
        return {"username": username, "error": "LeetCode API timed out", "found": False}
    except requests.exceptions.ConnectionError:
        logger.error("LeetCode API connection error | username=%s", username)
        return {"username": username, "error": "Cannot connect to LeetCode", "found": False}
    except Exception as exc:
        logger.error("Unexpected error | username=%s | error=%s", username, exc, exc_info=True)
        return {"username": username, "error": str(exc), "found": False}


def _parse_user_data(username: str, user: dict, recent: list, contest: Optional[dict]) -> dict:
    """Parse raw GraphQL response into a clean structured dict."""
    profile = user.get("profile", {})

    # Solved counts
    solved_map = {s["difficulty"]: s["count"] for s in user.get("submitStats", {}).get("acSubmissionNum", [])}
    solved = {
        "total": solved_map.get("All", 0),
        "easy": solved_map.get("Easy", 0),
        "medium": solved_map.get("Medium", 0),
        "hard": solved_map.get("Hard", 0),
    }

    # Topic breakdown — merge all difficulty tiers
    topics: dict[str, int] = {}
    tag_counts = user.get("tagProblemCounts", {})
    for tier in ("fundamental", "intermediate", "advanced"):
        for tag in tag_counts.get(tier, []):
            name = tag["tagName"]
            count = tag["problemsSolved"]
            if count > 0:
                topics[name] = topics.get(name, 0) + count
    # Sort by count descending
    topics = dict(sorted(topics.items(), key=lambda x: x[1], reverse=True))

    # Recent submissions — check which are from today
    today_ts = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    recent_parsed = []
    solved_today = []
    for sub in recent:
        ts = int(sub.get("timestamp", 0))
        sub_dt = datetime.fromtimestamp(ts, tz=UTC)
        entry = {
            "title": sub["title"],
            "slug": sub.get("titleSlug", ""),
            "timestamp": sub_dt.isoformat(),
            "solved_today": ts >= today_ts,
        }
        recent_parsed.append(entry)
        if ts >= today_ts:
            solved_today.append(sub["title"])

    # Contest info
    contest_info = {}
    if contest:
        contest_info = {
            "rating": round(contest.get("rating", 0)),
            "global_ranking": contest.get("globalRanking"),
            "contests_attended": contest.get("attendedContestsCount", 0),
            "top_percentage": round(contest.get("topPercentage", 0), 1),
        }

    return {
        "found": True,
        "username": username,
        "real_name": profile.get("realName") or username,
        "ranking": profile.get("ranking"),
        "school": profile.get("school", ""),
        "country": profile.get("countryName", ""),
        "solved": solved,
        "topics": topics,
        "recent_submissions": recent_parsed[:10],
        "solved_today": solved_today,
        "solved_today_count": len(solved_today),
        "contest": contest_info,
        "active_badge": (user.get("activeBadge") or {}).get("name", ""),
        "fetched_at": datetime.now(UTC).isoformat(),
    }


# ── Multi-student batch fetch ─────────────────────────────────────────────────

def fetch_class_stats(usernames: list[str], delay_seconds: float = 0.5) -> list[dict]:
    """
    Fetch stats for all students.
    Adds a small delay between requests to be polite to LeetCode servers.
    """
    results = []
    for i, username in enumerate(usernames):
        stats = fetch_student_stats(username.strip())
        results.append(stats)
        if i < len(usernames) - 1:
            time.sleep(delay_seconds)
    return results


# ── Report generator ──────────────────────────────────────────────────────────

def generate_class_report(usernames: list[str]) -> dict:
    """
    Generate a complete class-wide daily report.
    Returns structured data ready for dashboard display and email delivery.
    """
    logger.info("Generating class report | students=%d", len(usernames))
    student_stats = fetch_class_stats(usernames)

    found = [s for s in student_stats if s.get("found")]
    not_found = [s["username"] for s in student_stats if not s.get("found")]

    if not found:
        return {
            "error": "No valid LeetCode profiles found",
            "not_found": not_found,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # Class-wide totals
    total_solved = sum(s["solved"]["total"] for s in found)
    active_today = [s for s in found if s["solved_today_count"] > 0]

    # Topic aggregation across all students
    class_topics: dict[str, int] = {}
    for s in found:
        for topic, count in s.get("topics", {}).items():
            class_topics[topic] = class_topics.get(topic, 0) + count
    top_topics = dict(sorted(class_topics.items(), key=lambda x: x[1], reverse=True)[:10])

    # Rankings
    leaderboard = sorted(found, key=lambda x: x["solved"]["total"], reverse=True)

    # Today's activity
    today_activity = sorted(active_today, key=lambda x: x["solved_today_count"], reverse=True)

    # Difficulty distribution
    total_easy = sum(s["solved"]["easy"] for s in found)
    total_medium = sum(s["solved"]["medium"] for s in found)
    total_hard = sum(s["solved"]["hard"] for s in found)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "date": datetime.now(UTC).strftime("%B %d, %Y"),
        "summary": {
            "total_students": len(found),
            "active_today": len(active_today),
            "inactive_today": len(found) - len(active_today),
            "total_problems_solved_alltime": total_solved,
            "problems_solved_today": sum(s["solved_today_count"] for s in found),
            "average_solved": round(total_solved / len(found), 1) if found else 0,
            "difficulty": {
                "easy": total_easy,
                "medium": total_medium,
                "hard": total_hard,
            },
        },
        "leaderboard": [
            {
                "rank": i + 1,
                "username": s["username"],
                "real_name": s["real_name"],
                "total_solved": s["solved"]["total"],
                "easy": s["solved"]["easy"],
                "medium": s["solved"]["medium"],
                "hard": s["solved"]["hard"],
                "solved_today": s["solved_today_count"],
                "contest_rating": s.get("contest", {}).get("rating", 0),
            }
            for i, s in enumerate(leaderboard)
        ],
        "today_activity": [
            {
                "username": s["username"],
                "real_name": s["real_name"],
                "problems_today": s["solved_today_count"],
                "problems": s["solved_today"],
            }
            for s in today_activity
        ],
        "top_topics": top_topics,
        "not_found": not_found,
        "students": found,
    }

    logger.info(
        "Class report generated | students=%d | active_today=%d | total_solved=%d",
        len(found), len(active_today), total_solved,
    )
    return report
