import re
import requests

API_URL = "http://localhost:8000"


def test_summarizer_contract():
    text = (
        "We updated the server to emit structured events.\\n"
        "```python\\nprint('hello')\\n```\\n"
        "Then we added tests for the summarizer."
    )
    res = requests.post(f\"{API_URL}/summarize\", json={\"text\": text})
    res.raise_for_status()
    summary = res.json().get(\"summary\", \"\").strip()

    assert summary.startswith(\"I did\")
    assert \"I learned\" in summary
    assert \"Next\" in summary

    sentences = [s for s in re.split(r\"[.!?]+\", summary) if s.strip()]
    assert len(sentences) >= 3
