from unittest.mock import patch, MagicMock

import pytest
import requests

from pipeline import telegram_approval


def _resp(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.text = str(json_body)
    return r


def _callback(update_id, data, message_id, cbq_id="cbq-1"):
    return {"update_id": update_id,
            "callback_query": {"data": data, "message": {"message_id": message_id}, "id": cbq_id}}


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "final.mp4"
    path.write_bytes(b"fake-video")
    return str(path)


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_true_on_approve_callback(mock_post, mock_get, video):
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.return_value = _resp({"ok": True, "result": [_callback(1, "approve", 42)]})

    assert telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0) is True


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_false_on_reject_callback(mock_post, mock_get, video):
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.return_value = _resp({"ok": True, "result": [_callback(1, "reject", 42)]})

    assert telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0) is False


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_treats_unknown_callback_data_as_rejection(mock_post, mock_get, video):
    # Anything that is not an explicit approval must not publish.
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.return_value = _resp({"ok": True, "result": [_callback(1, "maybe_later", 42)]})

    assert telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0) is False


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_ignores_callbacks_for_other_messages(mock_post, mock_get, video):
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.side_effect = [
        _resp({"ok": True, "result": [_callback(1, "approve", 999)]}),
        _resp({"ok": True, "result": [_callback(2, "approve", 42, "cbq-2")]}),
    ]

    assert telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0) is True
    assert mock_get.call_count == 2


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_advances_the_update_offset(mock_post, mock_get, video):
    # Without an advancing offset, Telegram replays the same updates forever and
    # the loop spins until it times out.
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.side_effect = [
        _resp({"ok": True, "result": [_callback(7, "approve", 999)]}),
        _resp({"ok": True, "result": [_callback(8, "approve", 42, "cbq-2")]}),
    ]

    telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0)
    assert mock_get.call_args_list[1][1]["params"]["offset"] == 8


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_acknowledges_the_callback_query(mock_post, mock_get, video):
    # Without answerCallbackQuery the button keeps spinning in the Telegram UI.
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.return_value = _resp({"ok": True, "result": [_callback(1, "approve", 42, "cbq-9")]})

    telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0)

    answered = [c for c in mock_post.call_args_list if "answerCallbackQuery" in c[0][0]]
    assert answered and answered[0][1]["data"]["callback_query_id"] == "cbq-9"


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_times_out_to_false(mock_post, mock_get, video):
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.return_value = _resp({"ok": True, "result": []})

    result = telegram_approval.request_approval(video, "title", "desc",
                                                poll_interval_sec=0, timeout_sec=0)
    assert result is False


@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_raises_when_send_video_is_rejected(mock_post, video):
    mock_post.return_value = _resp({"ok": False, "description": "chat not found"}, status_code=400)
    with pytest.raises(telegram_approval.TelegramError, match="chat not found"):
        telegram_approval.request_approval(video, "title", "desc", poll_interval_sec=0)


@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_raises_when_credentials_are_missing(mock_post, video, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(telegram_approval.TelegramError, match="TELEGRAM_BOT_TOKEN"):
        telegram_approval.request_approval(video, "title", "desc")
    mock_post.assert_not_called()


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_uses_the_configured_default_timeout(mock_post, mock_get, video, monkeypatch):
    # On GitHub Actions every minute of this wait is a billed minute, so the
    # ceiling has to be settable from the environment.
    monkeypatch.setattr(telegram_approval, "DEFAULT_TIMEOUT_SEC", 0)
    mock_post.return_value = _resp({"ok": True, "result": {"message_id": 42}})
    mock_get.return_value = _resp({"ok": True, "result": []})

    assert telegram_approval.request_approval(video, "t", "d", poll_interval_sec=0) is False
    assert mock_get.call_count == 1


@patch("pipeline.telegram_approval.requests.post")
def test_notify_sends_the_text_to_the_configured_chat(mock_post):
    telegram_approval.notify("검증 예산 소진")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "sendMessage" in args[0]
    assert kwargs["data"]["chat_id"] == "12345"
    assert kwargs["data"]["text"] == "검증 예산 소진"


@patch("pipeline.telegram_approval.requests.post")
def test_notify_does_nothing_when_credentials_are_missing(mock_post, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    telegram_approval.notify("should not send")
    mock_post.assert_not_called()


@patch("pipeline.telegram_approval.requests.post")
def test_notify_swallows_network_errors(mock_post):
    mock_post.side_effect = requests.RequestException("boom")
    telegram_approval.notify("network is down")  # must not raise


@patch("pipeline.telegram_approval.requests.post")
def test_notify_logs_but_does_not_raise_when_telegram_rejects_the_message(mock_post, capsys):
    mock_post.return_value = _resp({"ok": False, "description": "bot was blocked"})
    telegram_approval.notify("should log a warning")  # must not raise
    assert "bot was blocked" in capsys.readouterr().out


@patch("pipeline.telegram_approval.requests.post")
def test_notify_logs_but_does_not_raise_on_non_200_status(mock_post, capsys):
    mock_post.return_value = _resp({"ok": False, "description": "unauthorized"}, status_code=401)
    telegram_approval.notify("should log a warning")  # must not raise
    assert "401" in capsys.readouterr().out


@patch("pipeline.telegram_approval.requests.post")
def test_notify_logs_but_does_not_raise_on_non_json_response(mock_post, capsys):
    r = MagicMock()
    r.status_code = 200
    r.json.side_effect = ValueError("not json")
    r.text = "<html>not json</html>"
    mock_post.return_value = r
    telegram_approval.notify("should log a warning")  # must not raise
    assert "notify failed" in capsys.readouterr().out
