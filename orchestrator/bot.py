"""Telegram conversation logic: ordering, review buttons, edits, payment instructions."""
import datetime as dt

from . import payments
from .texts import status_label, t


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class Bot:
    def __init__(self, tg, state, cfg, owner_id):
        self.tg, self.s, self.cfg, self.owner = tg, state, cfg, str(owner_id or "")

    # ------------------------------------------------------------- helpers
    def user(self, uid):
        u = self.s["users"].setdefault(str(uid), {"lang": None, "step": None, "draft": {}, "orders_done": 0})
        return u

    def L(self, uid):
        return self.user(uid).get("lang") or "ar"

    def notify_owner(self, text):
        if self.owner:
            try:
                self.tg.send(self.owner, text, silent=False)
            except Exception:  # noqa: BLE001
                pass

    def menu(self, uid):
        lang = self.L(uid)
        self.tg.send(uid, t(lang, "menu", brand=self.cfg["brand_name"]), [
            [(t(lang, "btn_new"), "new")],
            [(t(lang, "btn_prices"), "prices"), (t(lang, "btn_orders"), "orders")],
            [(t(lang, "btn_lang"), "lang_" + ("en" if lang == "ar" else "ar"))],
        ])

    def is_first_free(self, uid):
        if not self.cfg.get("first_order_free"):
            return False
        u = self.user(uid)
        has_any = any(o["uid"] == str(uid) and o["status"] != "cancelled" for o in self.s["orders"].values())
        return not has_any and not u.get("orders_done")

    def price_lines(self, lang):
        out = []
        for sec, v in self.cfg["lengths"].items():
            out.append(f"• {sec} {'ثانية' if lang == 'ar' else 'sec'}: <b>{v['price']}$</b>")
        return "\n".join(out)

    # ------------------------------------------------------------- dispatch
    def handle(self, upd):
        if "callback_query" in upd:
            cb = upd["callback_query"]
            uid = str(cb["from"]["id"])
            self.tg.answer_cb(cb["id"])
            return self.on_button(uid, cb.get("data", ""))
        msg = upd.get("message")
        if not msg or msg.get("chat", {}).get("type") != "private":
            return
        uid = str(msg["from"]["id"])
        text = (msg.get("text") or msg.get("caption") or "").strip()
        if uid == self.owner and text.startswith("/") and self.owner_cmd(text):
            return
        if text.startswith("/start"):
            u = self.user(uid)
            u["step"] = None
            if not u.get("lang"):
                return self.tg.send(uid, t("ar", "choose_lang"), [[("العربية", "lang_ar"), ("English", "lang_en")]])
            return self.menu(uid)
        return self.on_message(uid, msg, text)

    # ------------------------------------------------------------- buttons
    def on_button(self, uid, data):
        u, lang = self.user(uid), self.L(uid)
        if data.startswith("lang_"):
            u["lang"] = data[5:]
            return self.menu(uid)
        if data == "prices":
            key = "prices" if self.cfg.get("first_order_free") else "prices_nofree"
            return self.tg.send(uid, t(lang, key, lines=self.price_lines(lang), rev=self.cfg["max_revisions"]),
                                [[(t(lang, "btn_new"), "new")]])
        if data == "orders":
            return self.list_orders(uid)
        if data == "new":
            u["step"], u["draft"] = "desc", {}
            return self.tg.send(uid, t(lang, "ask_desc"))
        if data == "skip_photo" and u.get("step") == "photo":
            return self.ask_adlang(uid)
        if data.startswith("adlang_") and u.get("step") == "adlang":
            u["draft"]["ad_lang"] = data[7:]
            u["step"] = "len"
            rows = [[(t(lang, "len_btn", sec=sec, price=v["price"]), "len_" + sec)]
                    for sec, v in self.cfg["lengths"].items()]
            return self.tg.send(uid, t(lang, "ask_len"), rows)
        if data.startswith("len_") and u.get("step") == "len":
            sec = data[4:]
            if sec not in self.cfg["lengths"]:
                return
            u["draft"]["sec"] = sec
            u["step"] = "confirm"
            free = self.is_first_free(uid)
            price = t(lang, "free_label") if free else f"{self.cfg['lengths'][sec]['price']}$ USDT"
            adlang_name = {"ar": {"ar": "العربية", "en": "الإنجليزية"}, "en": {"ar": "Arabic", "en": "English"}}[lang][u["draft"]["ad_lang"]]
            return self.tg.send(uid, t(lang, "confirm", sec=sec, adlang=adlang_name,
                                       photo=t(lang, "yes") if u["draft"].get("photo") else t(lang, "no"), price=price),
                                [[(t(lang, "btn_confirm"), "confirm"), (t(lang, "btn_cancel"), "cancel")]])
        if data == "confirm" and u.get("step") == "confirm":
            return self.create_order(uid)
        if data == "cancel":
            u["step"], u["draft"] = None, {}
            self.tg.send(uid, t(lang, "cancelled"))
            return self.menu(uid)
        if ":" in data:
            action, oid = data.split(":", 1)
            o = self.s["orders"].get(oid)
            if not o or o["uid"] != uid:
                return
            return self.on_review(uid, o, action)
        return self.tg.send(uid, t(lang, "unknown"))

    def ask_adlang(self, uid):
        u, lang = self.user(uid), self.L(uid)
        u["step"] = "adlang"
        return self.tg.send(uid, t(lang, "ask_adlang"),
                            [[("العربية 🇸🇦", "adlang_ar"), ("English 🇬🇧", "adlang_en")]])

    # ------------------------------------------------------------- messages
    def on_message(self, uid, msg, text):
        u, lang = self.user(uid), self.L(uid)
        step = u.get("step")
        if step == "desc":
            if len(text) < 15:
                return self.tg.send(uid, t(lang, "desc_short"))
            u["draft"]["desc"] = text[:1500]
            u["step"] = "photo"
            return self.tg.send(uid, t(lang, "ask_photo"), [[(t(lang, "btn_skip"), "skip_photo")]])
        if step == "photo":
            if msg.get("photo"):
                u["draft"]["photo"] = msg["photo"][-1]["file_id"]
                return self.ask_adlang(uid)
            if msg.get("document", {}).get("mime_type", "").startswith("image/"):
                u["draft"]["photo"] = msg["document"]["file_id"]
                return self.ask_adlang(uid)
            return self.tg.send(uid, t(lang, "ask_photo"), [[(t(lang, "btn_skip"), "skip_photo")]])
        if step == "edit_text":
            oid = u.get("edit_order")
            o = self.s["orders"].get(oid)
            u["step"] = None
            if o and o["uid"] == uid and o["status"] == "review" and text:
                return self.queue_revision(uid, o, "edit", text[:800])
        return self.menu(uid)

    # ------------------------------------------------------------- orders
    def create_order(self, uid):
        u, lang = self.user(uid), self.L(uid)
        d = u["draft"]
        oid = str(self.s["next_order"])
        self.s["next_order"] += 1
        sec = d["sec"]
        free = self.is_first_free(uid)
        self.s["orders"][oid] = {
            "id": oid, "uid": uid, "desc": d["desc"], "photo": d.get("photo"), "ad_lang": d["ad_lang"],
            "sec": sec, "scenes": self.cfg["lengths"][sec]["scenes"],
            "price": 0 if free else self.cfg["lengths"][sec]["price"], "free": free,
            "status": "queued", "mode": "new", "feedback": "", "revisions": 0, "plan": None,
            "attempts": 0, "created": now_iso(), "preview_fid": None, "final_fid": None,
        }
        u["step"], u["draft"] = None, {}
        self.tg.send(uid, t(lang, "queued", oid=oid, eta=t(lang, "eta")))
        self.notify_owner(f"🆕 طلب جديد #{oid} · {sec}ث · {'مجاني' if free else str(self.s['orders'][oid]['price']) + '$'}")

    def on_review(self, uid, o, action):
        lang = self.L(uid)
        if o["status"] != "review":
            if o["status"] in ("queued", "generating"):
                return self.tg.send(uid, t(lang, "busy"))
            return
        if action == "ok":
            if o["free"]:
                return self.deliver(o, free=True)
            taken = [x["amount"] for x in self.s["orders"].values() if x["status"] == "awaiting_payment"]
            o["amount"] = payments.unique_amount(o["price"], taken)
            o["status"] = "awaiting_payment"
            o["pay_since"] = now_iso()
            self.tg.send(uid, t(lang, "pay", oid=o["id"], amount=f"{o['amount']:.2f}", token=self.cfg["payment_token"],
                                network=self.cfg["payment_network"], address=self.cfg["wallet_address"]))
            return self.notify_owner(f"👍 العميل اعتمد #{o['id']} وبانتظار دفع {o['amount']:.2f}$")
        if action in ("regen", "edit"):
            if o["revisions"] >= self.cfg["max_revisions"]:
                return self.tg.send(uid, t(lang, "rev_limit"))
            if action == "regen":
                return self.queue_revision(uid, o, "regen", "")
            u = self.user(uid)
            u["step"], u["edit_order"] = "edit_text", o["id"]
            return self.tg.send(uid, t(lang, "ask_edit"))

    def queue_revision(self, uid, o, mode, feedback):
        o["revisions"] += 1
        o["mode"], o["feedback"], o["status"], o["attempts"] = mode, feedback, "queued", 0
        left = self.cfg["max_revisions"] - o["revisions"]
        self.tg.send(uid, t(self.L(uid), "rev_queued", oid=o["id"], left=left))

    def deliver(self, o, free=False):
        lang = self.L(o["uid"])
        key = "free_done" if free else "paid"
        self.tg.send_video(o["uid"], o["final_fid"], caption=t(lang, key, oid=o["id"]))
        o["status"] = "done"
        o["done_at"] = now_iso()
        u = self.user(o["uid"])
        u["orders_done"] = u.get("orders_done", 0) + 1
        if free:
            self.menu(o["uid"])
        self.notify_owner(f"✅ تم تسليم #{o['id']}" + (" (مجاني)" if free else f" · دفع {o.get('amount', 0):.2f}$ 💰"))

    def list_orders(self, uid):
        lang = self.L(uid)
        mine = [o for o in self.s["orders"].values() if o["uid"] == uid][-6:]
        if not mine:
            return self.tg.send(uid, t(lang, "no_orders"), [[(t(lang, "btn_new"), "new")]])
        lines = "\n".join(f"#{o['id']} · {o['sec']}{'ث' if lang == 'ar' else 's'} · {status_label(lang, o['status'])}" for o in mine)
        rows = []
        for o in mine:
            if o["status"] == "awaiting_payment":
                lines += "\n\n" + t(lang, "pay", oid=o["id"], amount=f"{o['amount']:.2f}", token=self.cfg["payment_token"],
                                    network=self.cfg["payment_network"], address=self.cfg["wallet_address"])
        return self.tg.send(uid, t(lang, "orders_list", lines=lines), rows or [[(t(lang, "btn_new"), "new")]])

    # ------------------------------------------------------------- owner
    def owner_cmd(self, text):
        parts = text.split()
        cmd = parts[0].lower()
        if cmd == "/stats":
            os_ = self.s["orders"].values()
            cnt = {}
            for o in os_:
                cnt[o["status"]] = cnt.get(o["status"], 0) + 1
            earned = sum(o.get("amount", 0) for o in os_ if o["status"] == "done" and not o["free"])
            runs = "\n".join(f"• {a}: {r.get('status')} ({len(r.get('jobs', []))} مهام)" for a, r in self.s["kaggle_runs"].items()) or "• لا يوجد"
            self.tg.send(self.owner, "📊 <b>الإحصائيات</b>\n" + "\n".join(f"• {k}: {v}" for k, v in cnt.items())
                         + f"\n💰 المحصّل: {earned:.2f}$\n\n🖥 Kaggle:\n{runs}")
            return True
        if cmd == "/orders":
            open_ = [o for o in self.s["orders"].values() if o["status"] not in ("done", "cancelled")]
            lines = "\n".join(f"#{o['id']} · {o['status']} · {o['sec']}ث · rev {o['revisions']}" for o in open_[-20:]) or "لا يوجد"
            self.tg.send(self.owner, "📋 الطلبات المفتوحة:\n" + lines)
            return True
        if cmd == "/markpaid" and len(parts) > 1:
            o = self.s["orders"].get(parts[1].lstrip("#"))
            if o and o["status"] == "awaiting_payment" and o.get("final_fid"):
                self.deliver(o)
                self.tg.send(self.owner, f"تم تسليم #{o['id']} يدوياً.")
            else:
                self.tg.send(self.owner, "الطلب غير موجود أو مو بانتظار الدفع.")
            return True
        if cmd == "/cancel" and len(parts) > 1:
            o = self.s["orders"].get(parts[1].lstrip("#"))
            if o and o["status"] != "done":
                o["status"] = "cancelled"
                self.tg.send(self.owner, f"أُلغي #{o['id']}.")
            return True
        if cmd == "/help":
            self.tg.send(self.owner, "أوامر المالك:\n/stats الإحصائيات\n/orders الطلبات المفتوحة\n"
                                     "/markpaid 12 تسليم طلب دفع بمبلغ مختلف\n/cancel 12 إلغاء طلب")
            return True
        return False
