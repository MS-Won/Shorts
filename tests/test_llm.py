from unittest.mock import patch, MagicMock

import pytest

from pipeline import llm


def _fake_response(content=None, status_code=200):
    """A Gemini Interactions API response (steps -> model_output -> content)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = "error body"
    resp.json.return_value = {
        "id": "int_123",
        "status": "completed",
        "steps": [
            {"type": "user_input", "status": "done",
             "content": [{"type": "text", "text": "irrelevant"}]},
            {"type": "model_output", "status": "done",
             "content": content if content is not None else
             [{"type": "text", "text": "hello world"}]},
        ],
    }
    return resp


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@patch("pipeline.llm.requests.post")
def test_call_llm_returns_text_from_the_response(mock_post):
    mock_post.return_value = _fake_response()
    assert llm.call_llm("say hello") == "hello world"


@patch("pipeline.llm.requests.post")
def test_call_llm_skips_non_text_parts_and_finds_the_text_part(mock_post):
    mock_post.return_value = _fake_response(content=[
        {"type": "thought", "text": "hmm, thinking..."},
        {"type": "text", "text": "the answer"},
    ])
    assert llm.call_llm("think then answer") == "the answer"


@patch("pipeline.llm.requests.post")
def test_call_llm_raises_when_response_has_no_text_part(mock_post):
    mock_post.return_value = _fake_response(content=[{"type": "thought", "text": "..."}])
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=1)


@patch("pipeline.llm.requests.post")
def test_call_llm_sends_prompt_and_model_in_request_body(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    args, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert args[0] == llm.ENDPOINT
    assert body["model"] == llm.MODEL
    assert body["input"] == [{"type": "text", "text": "prompt"}]
    assert body["generation_config"]["thinking_config"]["thinking_budget"] == 0


@patch("pipeline.llm.requests.post")
def test_call_llm_posts_to_the_interactions_endpoint(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    args, _ = mock_post.call_args
    assert args[0] == "https://generativelanguage.googleapis.com/v1beta/interactions"


def test_default_model_is_gemini_flash_latest(monkeypatch):
    monkeypatch.delenv("GEMINI_TEXT_MODEL", raising=False)
    import importlib
    from pipeline import llm as llm_module

    importlib.reload(llm_module)
    try:
        assert llm_module.MODEL == "gemini-flash-latest"
    finally:
        # monkeypatch only restores GEMINI_TEXT_MODEL at test teardown, which
        # hasn't happened yet — reloading here while it's still deleted would
        # do nothing. Undo the monkeypatch now (restoring the real env) so
        # this reload actually puts llm_module.MODEL back for any tests that
        # run after this one in the same session.
        monkeypatch.undo()
        importlib.reload(llm_module)


@patch("pipeline.llm.requests.post")
def test_call_llm_sends_api_key_as_a_header_not_a_query_param(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    assert "params" not in kwargs


@patch("pipeline.llm.requests.post")
def test_call_llm_passes_system_prompt_and_max_tokens(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt", system="be terse", max_tokens=50)
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["system_instruction"] == "be terse"
    assert body["generation_config"]["max_output_tokens"] == 50


@patch("pipeline.llm.requests.post")
def test_call_llm_omits_system_instruction_when_not_given(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    assert "system_instruction" not in kwargs["json"]


@patch("pipeline.llm.requests.post")
def test_call_llm_requests_plain_text_output(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["response_format"] == {"type": "text"}


@patch("pipeline.llm.requests.post")
def test_call_llm_raises_on_non_200(mock_post):
    mock_post.return_value = _fake_response(status_code=400)
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=1)


@patch("pipeline.llm.requests.post")
def test_call_llm_raises_before_calling_the_api_when_key_is_missing(mock_post, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        llm.call_llm("prompt")
    mock_post.assert_not_called()


@patch("pipeline.llm.requests.post")
def test_call_llm_retries_then_raises_after_exhausting_retries(mock_post):
    mock_post.side_effect = RuntimeError("boom")
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=2)
    assert mock_post.call_count == 2


@patch("pipeline.llm.requests.post")
def test_call_llm_succeeds_on_retry_after_a_transient_failure(mock_post):
    mock_post.side_effect = [RuntimeError("transient"), _fake_response(content=[
        {"type": "text", "text": "recovered"},
    ])]
    assert llm.call_llm("prompt", retries=3) == "recovered"
    assert mock_post.call_count == 2


def test_strip_json_fences_drops_a_json_code_fence():
    raw = '```json\n{"a": 1}\n```'
    assert llm.strip_json_fences(raw) == '{"a": 1}'


def test_strip_json_fences_leaves_unfenced_text_alone():
    assert llm.strip_json_fences('{"a": 1}') == '{"a": 1}'
