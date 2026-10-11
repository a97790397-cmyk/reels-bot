"""Encrypted JSON state stored in the repo (state/state.enc).

The repo can be public: everything about customers lives only inside this
encrypted file, and the key comes from the STATE_PASSWORD secret.
"""
import base64
import hashlib
import json
import os

from cryptography.fernet import Fernet, InvalidToken

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "state", "state.enc")


def _fernet():
    pw = os.environ.get("STATE_PASSWORD", "")
    if len(pw) < 8:
        raise SystemExit("STATE_PASSWORD secret is missing or shorter than 8 characters")
    key = base64.urlsafe_b64encode(hashlib.sha256(("reels-arabi:" + pw).encode()).digest())
    return Fernet(key)


def empty_state():
    return {
        "version": 1,
        "tg_offset": 0,
        "users": {},          # uid -> {lang, step, draft, orders_done, edit_order}
        "orders": {},         # order_id -> order dict
        "next_order": 1,
        "kaggle_runs": {},    # account username -> {status, jobs:[...], pushed_at}
        "payments": {"last_block": 0, "used_tx": []},
        "library": [],        # [{file_id, prompt, order_id}]
        "heartbeat": "",
    }


def load():
    if not os.path.exists(STATE_PATH):
        return empty_state()
    with open(STATE_PATH, "rb") as f:
        blob = f.read()
    try:
        data = json.loads(_fernet().decrypt(blob).decode("utf-8"))
    except InvalidToken:
        raise SystemExit("Cannot decrypt state: STATE_PASSWORD changed? (restore it, or delete state/state.enc to start fresh)")
    base = empty_state()
    base.update(data)
    return base


def save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    raw = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    old = None
    if os.path.exists(STATE_PATH):
        try:
            old = _fernet().decrypt(open(STATE_PATH, "rb").read())
        except InvalidToken:
            old = None
    if old == raw:
        return False  # unchanged -> no commit
    with open(STATE_PATH, "wb") as f:
        f.write(_fernet().encrypt(raw))
    return True
