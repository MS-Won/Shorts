import json
import os
import time
import requests

_API_BASE = "https://api.telegram.org"


class TelegramApprovalError(Exception):
    pass


def _bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "")


def _send_video(video_path: str, caption: str) -> int:
    with open(video_path, "rb") as f:
        response = requests.post(
            f"{_API_BASE}/bot{_bot_token()}/sendVideo",
            data={
                "chat_id": _chat_id(),
                "caption": caption,
                "reply_markup": json.dumps({
                    "inline_keyboard": [[
                        {"text": "Approve ✅", "callback_data": "approve"},
                        {"text": "Reject ❌", "callback_data": "reject"},
                    ]]
                }),
            },
            files={"video": f},
            timeout=120,
        )
    if response.status_code != 200:
        raise TelegramApprovalError(
            f"sendVideo failed ({response.status_code}): {response.text}"
        )
    return response.json()["result"]["message_id"]


def _poll_for_decision(message_id: int, poll_interval_sec: int, timeout_sec: int) -> dict | None:
    """Poll getUpdates until a callback for our message from the configured
    chat is seen, or the timeout elapses. Returns the raw callback_query dict
    (so the caller can both read its decision and acknowledge it), or None.
    """
    elapsed = 0
    offset = None
    while elapsed <= timeout_sec:
        params = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        response = requests.get(f"{_API_BASE}/bot{_bot_token()}/getUpdates", params=params, timeout=30)
        for update in response.json().get("result", []):
            offset = update["update_id"] + 1
            callback = update.get("callback_query")
            if (
                callback
                and callback["message"]["message_id"] == message_id
                and str(callback["message"]["chat"]["id"]) == str(_chat_id())
            ):
                return callback
        if elapsed >= timeout_sec:
            break
        if poll_interval_sec:
            time.sleep(poll_interval_sec)
        elapsed += poll_interval_sec if poll_interval_sec else 1
    return None


def _answer_callback(callback_query_id: str) -> None:
    """Clear the tap spinner on the operator's inline keyboard button."""
    requests.post(
        f"{_API_BASE}/bot{_bot_token()}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id},
        timeout=30,
    )


def request_approval(video_path: str, title: str, description: str,
                      poll_interval_sec: int = 15, timeout_sec: int = 3600) -> bool:
    caption = f"{title}\n\n{description}"
    message_id = _send_video(video_path, caption)
    callback = _poll_for_decision(message_id, poll_interval_sec, timeout_sec)
    if callback is None:
        return False
    _answer_callback(callback["id"])
    return callback["data"] == "approve"
