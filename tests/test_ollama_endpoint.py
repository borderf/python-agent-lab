"""The same Python adapter must work from a host process and a container."""
import json

import pytest

from practice.enterprise_ai import ollama_local


@pytest.mark.parametrize("base,expected", [
    (None, "http://127.0.0.1:11434/api/chat"),
    ("http://host.docker.internal:11434/", "http://host.docker.internal:11434/api/chat"),
    ("https://model.example.test/ollama/", "https://model.example.test/ollama/api/chat"),
])
def test_ollama_endpoint_is_configurable(monkeypatch, base, expected):
    if base is None:
        monkeypatch.delenv("LAB_OLLAMA_URL", raising=False)
    else:
        monkeypatch.setenv("LAB_OLLAMA_URL", base)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"done": true}'

    def open_request(request, timeout):
        assert request.full_url == expected
        assert json.loads(request.data) == {"model": "fixture-model"}
        assert timeout == 60
        return Response()

    monkeypatch.setattr(ollama_local, "urlopen", open_request)
    assert ollama_local.post("/api/chat", {"model": "fixture-model"}) == {"done": True}


@pytest.mark.parametrize("base", ["", "file:///tmp/model", "http://user:secret@model.test",
                                   "http://model.test?key=test", "http://model.test#part"])
def test_bad_ollama_endpoint_never_sends_a_request(monkeypatch, base):
    monkeypatch.setenv("LAB_OLLAMA_URL", base)

    def forbidden(*args, **kwargs):
        pytest.fail("invalid configuration must fail before network access")

    monkeypatch.setattr(ollama_local, "urlopen", forbidden)
    with pytest.raises(ValueError, match="LAB_OLLAMA_URL"):
        ollama_local.post("/api/chat", {})
