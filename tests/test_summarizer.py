import re
import requests

API_URL = "http://localhost:8000"


def test_summarizer_contract():
    text = (
        "We updated the server to emit structured events.\\n"
        "```python\\nprint('hello')\\n```\\n"
        "Then we added tests for the summarizer."
    )
    res = requests.post(f"{API_URL}/summarize", json={"text": text})
    res.raise_for_status()
    summary = res.json().get("summary", "").strip()

    assert summary.startswith("I did")
    assert "I learned" in summary
    assert "Next" in summary
    assert re.search(r"server|structured", summary, re.IGNORECASE)


def test_summarizer_keeps_required_phrase():
    text = "We should display \"Hello World\" on the homepage and nothing else."
    res = requests.post(f"{API_URL}/summarize", json={"text": text})
    res.raise_for_status()
    summary = res.json().get("summary", "").strip()

    assert summary.startswith("I did")
    assert "hello world" in summary.lower()


def test_record_client_event():
    payload = {
        "type": "summary",
        "role": "system",
        "source": "summary",
        "content": "I did read a file."
    }
    res = requests.post(f"{API_URL}/session/invalid-session/event", json=payload)
    assert res.status_code == 404
