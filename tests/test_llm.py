from unittest.mock import patch, MagicMock
import pytest
from pipeline import llm


def _fake_response(text):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


@patch("pipeline.llm._client")
def test_call_llm_returns_text_from_first_content_block(mock_client):
    mock_client.messages.create.return_value = _fake_response("hello world")
    result = llm.call_llm("say hello")
    assert result == "hello world"


@patch("pipeline.llm._client")
def test_call_llm_passes_system_prompt_and_max_tokens(mock_client):
    mock_client.messages.create.return_value = _fake_response("ok")
    llm.call_llm("prompt", system="be terse", max_tokens=50)
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"] == "be terse"
    assert kwargs["max_tokens"] == 50
    assert kwargs["messages"] == [{"role": "user", "content": "prompt"}]


@patch("pipeline.llm._client")
def test_call_llm_retries_then_raises_after_exhausting_retries(mock_client):
    mock_client.messages.create.side_effect = RuntimeError("boom")
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=2)
    assert mock_client.messages.create.call_count == 2
