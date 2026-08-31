from unittest.mock import patch, MagicMock
from pipeline import telegram_approval


def _resp(json_body):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_body
    return r


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_true_on_approve_callback(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": [
        {"update_id": 1, "callback_query": {"data": "approve",
         "message": {"message_id": 42}, "id": "cbq-1"}}
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
        {"update_id": 1, "callback_query": {"data": "reject",
         "message": {"message_id": 42}, "id": "cbq-1"}}
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
            {"update_id": 1, "callback_query": {"data": "approve",
             "message": {"message_id": 999}, "id": "cbq-1"}}
        ]}),
        _resp({"result": [
            {"update_id": 2, "callback_query": {"data": "approve",
             "message": {"message_id": 42}, "id": "cbq-2"}}
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
