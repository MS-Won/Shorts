from unittest.mock import patch, MagicMock
import pytest
from pipeline import llm


def _block(kind, **fields):
    """A stand-in for an SDK content block (TextBlock, ThinkingBlock, ...)."""
    return MagicMock(type=kind, **fields)


def _fake_response(*blocks):
    resp = MagicMock()
    resp.content = list(blocks)
    return resp


@patch("pipeline.llm._client")
def test_call_llm_returns_text_from_text_block(mock_client):
    mock_client.messages.create.return_value = _fake_response(_block("text", text="hello world"))
    result = llm.call_llm("say hello")
    assert result == "hello world"


@patch("pipeline.llm._client")
def test_call_llm_skips_thinking_block_and_returns_the_text_block(mock_client):
    # Thinking is on by default on every current Claude model, so the first
    # content block is often a ThinkingBlock, which has no `.text` at all.
    mock_client.messages.create.return_value = _fake_response(
        _block("thinking", thinking="hmm..."),
        _block("text", text="the answer"),
    )
    assert llm.call_llm("think then answer") == "the answer"


@patch("pipeline.llm._client")
def test_call_llm_raises_when_response_has_no_text_block(mock_client):
    mock_client.messages.create.return_value = _fake_response(_block("thinking", thinking="..."))
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=1)


@patch("pipeline.llm._client")
def test_call_llm_passes_system_prompt_and_max_tokens(mock_client):
    mock_client.messages.create.return_value = _fake_response(_block("text", text="ok"))
    llm.call_llm("prompt", system="be terse", max_tokens=50)
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"] == "be terse"
    assert kwargs["max_tokens"] == 50
    assert kwargs["messages"] == [{"role": "user", "content": "prompt"}]
    assert kwargs["model"] == llm.MODEL


@patch("pipeline.llm._client")
def test_call_llm_omits_system_when_not_given(mock_client):
    mock_client.messages.create.return_value = _fake_response(_block("text", text="ok"))
    llm.call_llm("prompt")
    _, kwargs = mock_client.messages.create.call_args
    assert "system" not in kwargs


@patch("pipeline.llm._client")
def test_call_llm_retries_then_raises_after_exhausting_retries(mock_client):
    mock_client.messages.create.side_effect = RuntimeError("boom")
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=2)
    assert mock_client.messages.create.call_count == 2


@patch("pipeline.llm._client")
def test_call_llm_succeeds_on_retry_after_a_transient_failure(mock_client):
    mock_client.messages.create.side_effect = [
        RuntimeError("transient"),
        _fake_response(_block("text", text="recovered")),
    ]
    assert llm.call_llm("prompt", retries=3) == "recovered"
    assert mock_client.messages.create.call_count == 2
