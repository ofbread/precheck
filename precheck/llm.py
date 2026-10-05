import json
import time
import urllib.request


def openai_compatible(endpoint, model, max_tokens=400, api_key=None, timeout=180):
    """Return a function that sends a prompt to an OpenAI-compatible chat API and returns the reply."""
    url = endpoint.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def call(prompt):
        body = json.dumps({"model": model, "temperature": 0, "max_tokens": max_tokens,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        for attempt in range(6):
            try:
                request = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read())["choices"][0]["message"]["content"] or ""
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(min(2 ** attempt, 16))
    return call
