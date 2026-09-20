from types import SimpleNamespace

import pytest

from graph import models
from graph.state import new_state


def _client_returning(content):
    message = SimpleNamespace(content=content)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)
    create = lambda **_: response  # noqa: E731
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.mark.parametrize("content", [None, "", "   \n"])
def test_empty_completion_raises_naming_task_and_alias(monkeypatch, content):
    monkeypatch.setattr(models, "_get_client", lambda: _client_returning(content))

    with pytest.raises(RuntimeError, match=r"concept_agent.*auto/best-free"):
        models.call_model("concept_agent", [{"role": "user", "content": "hi"}], new_state())


def test_usable_completion_is_returned_and_logged(monkeypatch):
    monkeypatch.setattr(models, "_get_client", lambda: _client_returning("a question"))
    state = new_state()

    assert models.call_model("concept_agent", [], state) == "a question"
    assert len(state["model_calls"]) == 1


def test_client_has_bounded_retries_and_timeout(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://example.invalid/v1")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "k")
    monkeypatch.setattr(models, "_client", None)

    client = models._get_client()
    monkeypatch.setattr(models, "_client", None)

    assert client.max_retries == models._MAX_RETRIES
    assert client.timeout == models._TIMEOUT_SECONDS


def test_pacing_agent_has_no_model_alias():
    assert "pacing_agent" not in models.MODEL_CONFIG
