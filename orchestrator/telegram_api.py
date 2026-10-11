"""Tiny Telegram Bot API client (requests only)."""
import json
import os

import requests


class Telegram:
    def __init__(self, token):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}/"

    def _call(self, method, data=None, files=None, timeout=60):
        r = requests.post(self.base + method, data=data, files=files, timeout=timeout)
        try:
            j = r.json()
        except ValueError:
            raise RuntimeError(f"telegram {method}: HTTP {r.status_code}")
        if not j.get("ok"):
            raise RuntimeError(f"telegram {method}: {j.get('description')}")
        return j["result"]

    @staticmethod
    def kb(rows):
        """rows: [[(text, callback_data), ...], ...] -> inline keyboard json"""
        return json.dumps({"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]})

    def get_updates(self, offset):
        return self._call("getUpdates", {"offset": offset, "timeout": 0,
                                         "allowed_updates": json.dumps(["message", "callback_query"])})

    def send(self, chat_id, text, rows=None, silent=False):
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
                "disable_notification": silent}
        if rows:
            data["reply_markup"] = self.kb(rows)
        return self._call("sendMessage", data)

    def answer_cb(self, cb_id, text=None):
        try:
            self._call("answerCallbackQuery", {"callback_query_id": cb_id, **({"text": text} if text else {})})
        except Exception:  # noqa: BLE001 - old callbacks expire, not important
            pass

    def send_video(self, chat_id, video, caption="", rows=None, silent=False):
        """video: local path or an existing file_id. Returns (message, file_id)."""
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML",
                "supports_streaming": True, "disable_notification": silent}
        if rows:
            data["reply_markup"] = self.kb(rows)
        if os.path.exists(str(video)):
            with open(video, "rb") as f:
                msg = self._call("sendVideo", data, files={"video": f}, timeout=300)
        else:
            data["video"] = video
            msg = self._call("sendVideo", data)
        fid = (msg.get("video") or msg.get("document") or {}).get("file_id")
        return msg, fid

    def download(self, file_id, dest):
        info = self._call("getFile", {"file_id": file_id})
        url = f"https://api.telegram.org/file/bot{self.token}/{info['file_path']}"
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
