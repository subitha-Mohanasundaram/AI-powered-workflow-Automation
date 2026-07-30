import sys, json
sys.path.insert(0, 'backend')

from dotenv import load_dotenv
load_dotenv('.env')

from app.config import settings
from app.services.ai import _supports_json_mode, _extract_json

print("=== LLM Configuration ===")
print(f"  AI_BASE_URL : {settings.ai_base_url}")
print(f"  AI_MODEL    : {settings.ai_model}")
key_status = f"SET ({len(settings.ai_api_key)} chars)" if settings.ai_api_key else "NOT SET ❌ — add your Groq key to .env"
print(f"  AI_API_KEY  : {key_status}")
print(f"  AI_TIMEOUT  : {settings.ai_timeout_seconds}s")
print()

print("=== Provider Checks ===")
print(f"  JSON mode forced : {_supports_json_mode()} (False is correct for Groq — uses prompt-based JSON)")
print()

print("=== _extract_json Tests ===")
tests = [
    ('{"workflow_name": "test", "steps": []}', "raw JSON"),
    ('```json\n{"workflow_name": "test", "steps": []}\n```', "markdown fenced ```json"),
    ('```\n{"workflow_name": "test", "steps": []}\n```', "plain fence ```"),
    ('Here is the result:\n{"workflow_name": "test", "steps": []}', "prefixed text"),
]
all_pass = True
for text, label in tests:
    try:
        result = _extract_json(text)
        parsed = json.loads(result)
        print(f"  PASS  {label}")
    except Exception as e:
        print(f"  FAIL  {label} -> {e}")
        all_pass = False

print()
if all_pass:
    print("All checks passed. ✅")
    print()
    if not settings.ai_api_key:
        print("Next step: Add your Groq API key to .env")
        print("  1. Go to https://console.groq.com/keys")
        print("  2. Create a free API key")
        print("  3. Set AI_API_KEY=gsk_... in your .env file")
    else:
        print("Groq key is set. Testing live connection...")
        try:
            from app.services.ai import _get_client
            client = _get_client()
            resp = client.chat.completions.create(
                model=settings.ai_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}]
            )
            print(f"  Live call: OK ✅ — model={resp.model}, response='{resp.choices[0].message.content}'")
        except Exception as e:
            print(f"  Live call: FAILED ❌ — {e}")
else:
    print("Some checks failed. ❌")
