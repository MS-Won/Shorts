import pytest
from unittest.mock import patch, MagicMock
from pipeline import telegram_approval

CHAT_ID = "555111"


def _resp(json_body, status_code=200, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.text = text
    return r


@pytest.fixture(autouse=True)
def _telegram_chat_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_true_on_approve_callback(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": [
        {"update_id": 1, "callback_query": {"data": "approve", "id": "cbq-1",
         "message": {"message_id": 42, "chat": {"id": CHAT_ID}}}}
    ]})

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is True


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_false_on_reject_callback(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": [
        {"update_id": 1, "callback_query": {"data": "reject", "id": "cbq-1",
         "message": {"message_id": 42, "chat": {"id": CHAT_ID}}}}
    ]})

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is False


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_ignores_callbacks_for_other_messages(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.side_effect = [
        _resp({"result": [
            {"update_id": 1, "callback_query": {"data": "approve", "id": "cbq-1",
             "message": {"message_id": 999, "chat": {"id": CHAT_ID}}}}
        ]}),
        _resp({"result": [
            {"update_id": 2, "callback_query": {"data": "approve", "id": "cbq-2",
             "message": {"message_id": 42, "chat": {"id": CHAT_ID}}}}
        ]}),
    ]

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is True
    assert mock_get.call_count == 2


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_ignores_callbacks_from_other_chats(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.side_effect = [
        _resp({"result": [
            {"update_id": 1, "callback_query": {"data": "approve", "id": "cbq-1",
             "message": {"message_id": 42, "chat": {"id": "999999"}}}}
        ]}),
        _resp({"result": [
            {"update_id": 2, "callback_query": {"data": "approve", "id": "cbq-2",
             "message": {"message_id": 42, "chat": {"id": CHAT_ID}}}}
        ]}),
    ]

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is True
    assert mock_get.call_count == 2


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_times_out_to_false(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": []})

    result = telegram_approval.request_approval(str(video_path), "title", "desc",
                                                  poll_interval_sec=0, timeout_sec=0)
    assert result is False


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_send_video_raises_on_non_200_response(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({}, status_code=413, text="Request Entity Too Large")

    with pytest.raises(telegram_approval.TelegramApprovalError):
        telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    mock_get.assert_not_called()


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_answers_callback_query_after_decision(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": [
        {"update_id": 1, "callback_query": {"data": "approve", "id": "cbq-42",
         "message": {"message_id": 42, "chat": {"id": CHAT_ID}}}}
    ]})

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is True

    answer_calls = [
        call for call in mock_post.call_args_list
        if call.args and "answerCallbackQuery" in call.args[0]
    ]
    assert len(answer_calls) == 1
    assert answer_calls[0].kwargs["json"] == {"callback_query_id": "cbq-42"}


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_does_not_answer_callback_on_timeout(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": []})

    telegram_approval.request_approval(str(video_path), "title", "desc",
                                        poll_interval_sec=0, timeout_sec=0)

    answer_calls = [
        call for call in mock_post.call_args_list
        if call.args and "answerCallbackQuery" in call.args[0]
    ]
    assert len(answer_calls) == 0
