"""The human approval gate (spec §5 step ⑤).

Everything upstream of this is automated and has already cost money; this is
the one place a person still decides. Anything that is not an explicit approval
— a rejection, a timeout, an unrecognised button — means "do not publish".
"""

import json
import os
import time

import requests

API_BASE = "https://api.telegram.org"

APPROVE = "approve"
REJECT = "reject"

# The pipeline blocks here, and on GitHub Actions the job is billed for every
# minute of that wait — so the ceiling is configurable per environment.
DEFAULT_TIMEOUT_SEC = int(os.environ.get("APPROVAL_TIMEOUT_SEC", "3600"))


class TelegramError(Exception):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise TelegramError(f"{name} is not set")
    return value


def _check(response, what: str) -> dict:
    body = response.json()
    if response.status_code != 200 or not body.get("ok", False):
        raise TelegramError(
            f"{what} failed ({response.status_code}): {body.get('description') or response.text}"
        )
    return body


def _send_video(token: str, chat_id: str, video_path: str, caption: str) -> int:
    with open(video_path, "rb") as f:
        response = requests.post(
            f"{API_BASE}/bot{token}/sendVideo",
            data={
                "chat_id": chat_id,
                "caption": caption,
                "reply_markup": json.dumps({
                    "inline_keyboard": [[
                        {"text": "Approve ✅", "callback_data": APPROVE},
                        {"text": "Reject ❌", "callback_data": REJECT},
                    ]]
                }),
            },
            files={"video": f},
            timeout=120,
        )
    return _check(response, "sendVideo")["result"]["message_id"]


def _answer_callback(token: str, callback_query_id: str) -> None:
    # Best effort: the decision is already made, so a failure here must not
    # change the outcome — it only clears the spinner on the button.
    try:
        requests.post(
            f"{API_BASE}/bot{token}/answerCallbackQuery",
            data={"callback_query_id": callback_query_id},
            timeout=30,
        )
    except requests.RequestException:
        pass


def _poll_for_decision(token: str, message_id: int, poll_interval_sec: int,
                       timeout_sec: int) -> str | None:
    # Measured against the clock, not by accumulating the sleep interval: the
    # polling requests themselves take real time, and a run that hangs must
    # still hit its deadline.
    deadline = time.monotonic() + timeout_sec
    offset = None
    while True:
        params = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        response = requests.get(f"{API_BASE}/bot{token}/getUpdates", params=params, timeout=30)
        for update in _check(response, "getUpdates").get("result", []):
            offset = update["update_id"] + 1
            callback = update.get("callback_query")
            if callback and callback.get("message", {}).get("message_id") == message_id:
                _answer_callback(token, callback.get("id", ""))
                return callback.get("data")

        if time.monotonic() >= deadline:
            return None
        if poll_interval_sec:
            time.sleep(poll_interval_sec)


def request_approval(video_path: str, title: str, description: str,
                     poll_interval_sec: int = 15, timeout_sec: int | None = None) -> bool:
    if timeout_sec is None:
        timeout_sec = DEFAULT_TIMEOUT_SEC
    token = _require("TELEGRAM_BOT_TOKEN")
    chat_id = _require("TELEGRAM_CHAT_ID")

    caption = f"{title}\n\n{description}"
    message_id = _send_video(token, chat_id, video_path, caption)
    decision = _poll_for_decision(token, message_id, poll_interval_sec, timeout_sec)
    return decision == APPROVE


def notify(text: str) -> None:
    """A one-way heads-up — no buttons, no wait for a reply.

    Used when the pipeline stops itself (validation budget/checkpoint) or
    hits an unhandled failure, so a person finds out without going to check
    the Actions log. Best-effort: this fires from places where something has
    already gone wrong, so a failure here must never crash the caller and
    bury the real reason.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"{API_BASE}/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=30,
        )
    except requests.RequestException:
        pass
