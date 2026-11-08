"""Minimal non-streaming client for a local Ollama service."""
from http.client import IncompleteRead
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def decode_json(raw: bytes | str):
    """Preserve object pairs until duplicates have been rejected (chapter 7)."""
    def unique_fields(pairs):
        fields = {}
        for key, value in pairs:
            if key in fields:
                raise ValueError(f"duplicate JSON field: {key}")
            fields[key] = value
        return fields

    return json.loads(raw, object_pairs_hook=unique_fields)


def post(path: str, payload: dict) -> dict:
    request = Request("http://127.0.0.1:11434" + path,
                      data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            result = decode_json(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"{path}: HTTP {exc.code}; check model and capabilities") from exc
    except (URLError, TimeoutError, ConnectionError, IncompleteRead) as exc:
        raise RuntimeError(f"{path}: local Ollama unavailable or timed out") from exc
    if not isinstance(result, dict) or "error" in result:
        raise ValueError(f"{path}: invalid response")
    return result


def assistant_message(response: dict) -> dict:
    if response.get("done") is not True or response.get("done_reason") == "length":
        raise ValueError("incomplete model response")
    message = response.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("invalid assistant message")
    return message
