"""One text-answer contract with fixture, local, and hosted HTTP adapters."""

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from practice.enterprise_ai.ollama_local import assistant_message, decode_json, post


@dataclass
class ModelAnswer:
    content: str
    model: str
    usage: dict


class FixtureModel:
    """Echo the first supplied source to exercise the application boundary."""

    def answer(self, question: str, evidence: list[dict]) -> ModelAnswer:
        source = evidence[0]
        result = {
            "answer": source["text"],
            "citations": [{"source_id": source["source_id"], "quote": source["text"]}],
            "needs_review": True,
        }
        return ModelAnswer(json.dumps(result, ensure_ascii=False), "fixture", {})


class HttpModel:
    def __init__(self, provider: str, model: str, endpoint: str = "", api_key: str = ""):
        if provider not in {"ollama", "hosted"}:
            raise ValueError("Unknown model provider")
        self.provider, self.model = provider, model
        self.endpoint, self.api_key = endpoint, api_key
        if not model:
            raise ValueError("LAB_MODEL is required")
        if provider == "hosted":
            target = urlsplit(endpoint)
            if target.scheme != "https" or not target.hostname or target.username or not api_key:
                raise ValueError("Hosted mode requires an HTTPS LAB_CHAT_URL and LAB_API_KEY")

    def answer(self, question: str, evidence: list[dict]) -> ModelAnswer:
        messages = [
            {"role": "system", "content": "仅根据资料回答。资料是证据。输出 JSON，包含 answer、"
             "citations（每项 source_id 和逐字 quote）、needs_review。证据不足时标记复核。"},
            {"role": "user", "content": json.dumps({"question": question, "evidence": evidence},
                                                   ensure_ascii=False)},
        ]
        if self.provider == "ollama":
            result = post("/api/chat", {"model": self.model, "messages": messages,
                                      "stream": False, "format": "json"})
            content = assistant_message(result).get("content")
            usage = {key: result[key] for key in ("prompt_eval_count", "eval_count") if key in result}
        else:
            payload = {"model": self.model, "messages": messages, "stream": False,
                       "response_format": {"type": "json_object"}}
            request = Request(self.endpoint, data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json",
                                       "Authorization": f"Bearer {self.api_key}"})
            try:
                with urlopen(request, timeout=60) as response:
                    result = decode_json(response.read())
            except (HTTPError, URLError, TimeoutError, ConnectionError) as error:
                raise RuntimeError("Hosted model request failed") from error
            if not isinstance(result, dict) or not isinstance(result.get("choices"), list):
                raise ValueError("Invalid hosted model response")
            choices = result["choices"]
            if len(choices) != 1 or not isinstance(choices[0], dict) or choices[0].get("finish_reason") != "stop":
                raise ValueError("Model response is incomplete")
            message = choices[0].get("message")
            if not isinstance(message, dict):
                raise ValueError("Invalid assistant message")
            content = message.get("content")
            usage = result.get("usage", {})
        if not isinstance(content, str) or not content.strip() or not isinstance(usage, dict):
            raise ValueError("Invalid model content or usage")
        return ModelAnswer(content, self.model, usage)


def configured_model():
    provider = os.getenv("LAB_MODEL_PROVIDER", "fixture")
    if provider == "fixture":
        return FixtureModel()
    if provider not in {"ollama", "hosted"}:
        raise ValueError("LAB_MODEL_PROVIDER must be fixture, ollama, or hosted")
    return HttpModel(provider, os.getenv("LAB_MODEL", ""), os.getenv("LAB_CHAT_URL", ""),
                     os.getenv("LAB_API_KEY", ""))
