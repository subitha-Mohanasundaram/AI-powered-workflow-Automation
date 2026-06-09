import requests
import json

url = "https://leetcode.com/graphql"
headers = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

query = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { realName ranking }
    submitStats {
      acSubmissionNum {
        difficulty
        count
      }
    }
    tagProblemCounts {
      advanced { tagName problemsSolved }
      intermediate { tagName problemsSolved }
      fundamental { tagName problemsSolved }
    }
  }
  recentAcSubmissionList(username: $username, limit: 5) {
    title
    timestamp
  }
}
"""

resp = requests.post(
    url,
    json={"query": query, "variables": {"username": "neal_wu"}},
    headers=headers,
    timeout=10
)
data = resp.json()
user = data["data"]["matchedUser"]
print("Username:", user["username"])
print("Ranking:", user["profile"]["ranking"])
print("Solved:", {s["difficulty"]: s["count"] for s in user["submitStats"]["acSubmissionNum"]})
recent = data["data"]["recentAcSubmissionList"]
print("Recent:", [s["title"] for s in recent])
print()
print("LeetCode API works!")
