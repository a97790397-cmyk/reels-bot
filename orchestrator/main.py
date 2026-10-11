"""One 'tick' of the system. GitHub Actions runs this every 5 minutes.

Each tick: answer Telegram for ~4.5 minutes, collect finished Kaggle runs, assemble videos,
start new Kaggle runs for queued orders, and check the wallet for payments.
"""
import datetime as dt
import glob
import json
import os
import shutil
import tempfile
import time
import traceback

from . import assemble, payments, state as st
from .bot import Bot, now_iso
from .kaggle_runner import Account, accounts
from .telegram_api import Telegram
from .texts import t

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOP_SECONDS = int(os.environ.get("LOOP_SECONDS", "270"))


def log(*a):
    # Logs of a public repo are public: never print customer data here.
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_cfg():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ telegram
def poll_telegram(tg, bot, s):
    try:
        ups = tg.get_updates(s["tg_offset"])
    except Exception as e:  # noqa: BLE001
        log("telegram poll failed:", type(e).__name__)
        return 0
    for u in ups:
        s["tg_offset"] = u["update_id"] + 1
        try:
            bot.handle(u)
        except Exception:  # noqa: BLE001
            log("handler error\n" + traceback.format_exc(limit=3))
    return len(ups)


# ------------------------------------------------------------------ kaggle
def hours_since(iso):
    try:
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso)).total_seconds() / 3600
    except Exception:  # noqa: BLE001
        return 0


def handle_results(tg, bot, s, cfg, run, outdir):
    res_files = glob.glob(os.path.join(outdir, "**", "results.json"), recursive=True)
    results, base = {}, outdir
    if res_files:
        base = os.path.dirname(res_files[0])
        with open(res_files[0], encoding="utf-8") as f:
            results = json.load(f)
    storage = os.environ.get("STORAGE_CHAT_ID") or bot.owner
    label = "@" + cfg["bot_username"]
    for job_id, oid in run["jobs"].items():
        o = s["orders"].get(oid)
        if not o or o["status"] != "generating" or o.get("job_id") != job_id:
            continue
        r = results.get(job_id, {})
        clips = [os.path.join(base, c) for c in r.get("clips", [])]
        clips = [c for c in clips if os.path.exists(c)]
        try:
            if not r.get("ok") or len(clips) < o["scenes"]:
                raise RuntimeError(r.get("error") or "missing clips")
            work = tempfile.mkdtemp(prefix=f"asm_{oid}_")
            photo = None
            if o.get("photo"):
                try:
                    photo = tg.download(o["photo"], os.path.join(work, "photo.jpg"))
                except Exception:  # noqa: BLE001
                    photo = None
            plan = r.get("plan") or {}
            prev = assemble.build(clips, plan, o["ad_lang"], os.path.join(work, "preview.mp4"),
                                  os.path.join(work, "p"), photo, mode="preview", label=label)
            final = assemble.build(clips, plan, o["ad_lang"], os.path.join(work, "final.mp4"),
                                   os.path.join(work, "f"), photo, mode="badge" if o["free"] else "clean", label=label)
            _, final_fid = tg.send_video(storage, final, caption=f"#{oid} final (rev {o['revisions']})", silent=True)
            lang = bot.L(o["uid"])
            _, prev_fid = tg.send_video(o["uid"], prev, caption=t(lang, "preview_caption", oid=oid), rows=[
                [(t(lang, "btn_ok"), f"ok:{oid}")],
                [(t(lang, "btn_regen"), f"regen:{oid}"), (t(lang, "btn_edit"), f"edit:{oid}")],
            ])
            o.update({"plan": plan, "status": "review", "final_fid": final_fid, "preview_fid": prev_fid,
                      "reviewed_at": now_iso()})
            shutil.rmtree(work, ignore_errors=True)
            log("delivered preview for order", oid)
        except Exception as e:  # noqa: BLE001
            o["attempts"] = o.get("attempts", 0) + 1
            log("order", oid, "failed:", type(e).__name__)
            if o["attempts"] < 2:
                o["status"] = "queued"
            else:
                o["status"] = "failed"
                try:
                    tg.send(o["uid"], t(bot.L(o["uid"]), "failed", oid=oid))
                except Exception:  # noqa: BLE001
                    pass
                bot.notify_owner(f"⚠️ فشل تجهيز #{oid} مرتين: {str(e)[:200]}")


def process_kaggle(tg, bot, s, cfg):
    kc = cfg["kaggle"]
    accs = accounts()
    if not accs:
        log("no kaggle accounts configured")
        return
    for a in accs:
        acc = Account(a["username"], a["key"], kc["kernel_slug"])
        run = s["kaggle_runs"].get(a["username"])
        try:
            if run and run.get("status") == "running":
                stt = acc.status()
                too_long = hours_since(run["pushed_at"]) > kc["run_timeout_hours"] + 3
                log("kaggle", a["username"][:3] + "***", "status:", stt)
                if stt in ("complete", "error", "cancelled") and hours_since(run["pushed_at"]) < 0.2:
                    stt = "running"  # status may still describe the previous version right after a push
                if stt in ("complete", "error", "cancelled") or too_long:
                    out = tempfile.mkdtemp(prefix="kout_")
                    try:
                        acc.download(out)
                    except Exception as e:  # noqa: BLE001
                        log("download failed:", type(e).__name__)
                    handle_results(tg, bot, s, cfg, run, out)
                    shutil.rmtree(out, ignore_errors=True)
                    run["status"] = "idle"
                    if stt == "error":
                        bot.notify_owner("⚠️ تشغيل Kaggle انتهى بخطأ. شوف سجل النوتبوك reels-gen في حسابك.")
            run = s["kaggle_runs"].get(a["username"])
            if not run or run.get("status") != "running":
                start_run(acc, bot, s, cfg)
        except Exception as e:  # noqa: BLE001
            log("kaggle account error:", type(e).__name__, str(e)[:200])
        finally:
            acc.close()


def start_run(acc, bot, s, cfg):
    kc = cfg["kaggle"]
    queued = sorted((o for o in s["orders"].values() if o["status"] == "queued"), key=lambda o: int(o["id"]))
    if not queued:
        return
    jobs, mapping, clips = [], {}, 0
    for o in queued:
        if jobs and clips + o["scenes"] > kc["max_clips_per_run"]:
            break
        job_id = f"o{o['id']}r{o['revisions']}a{o.get('attempts', 0)}"
        jobs.append({"job_id": job_id, "desc": o["desc"], "lang": o["ad_lang"], "scenes": o["scenes"],
                     "mode": o["mode"], "feedback": o.get("feedback", ""),
                     "prev_plan": o.get("plan") if o["mode"] == "edit" else None})
        mapping[job_id] = o["id"]
        clips += o["scenes"]
    settings = {"steps": kc["inference_steps"], "time_budget_s": int(kc["run_timeout_hours"] * 3600 - 1800),
                "timeout_s": int(kc["run_timeout_hours"] * 3600), "accelerator": kc.get("accelerator", "")}
    acc.push(jobs, settings)
    for job_id, oid in mapping.items():
        s["orders"][oid]["status"] = "generating"
        s["orders"][oid]["job_id"] = job_id
    s["kaggle_runs"][acc.username] = {"status": "running", "jobs": mapping, "pushed_at": now_iso()}
    log(f"pushed {len(jobs)} job(s), {clips} clip(s)")


# ------------------------------------------------------------------ payments
def process_payments(bot, s, cfg):
    waiting = {o["id"]: o["amount"] for o in s["orders"].values() if o["status"] == "awaiting_payment"}
    if not waiting:
        s["payments"]["last_block"] = 0
        return
    try:
        transfers, last = payments.scan(cfg["wallet_address"], s["payments"]["last_block"])
    except Exception as e:  # noqa: BLE001
        log("payment scan failed:", type(e).__name__)
        return
    s["payments"]["last_block"] = last
    for oid, tx in payments.match(transfers, waiting, set(s["payments"]["used_tx"])):
        s["payments"]["used_tx"] = (s["payments"]["used_tx"] + [tx])[-500:]
        o = s["orders"][oid]
        o["paid_tx"] = tx
        try:
            bot.deliver(o)
            log("payment matched for order", oid)
        except Exception as e:  # noqa: BLE001
            log("deliver failed:", type(e).__name__)


# ------------------------------------------------------------------ main
def main():
    cfg = load_cfg()
    token, owner = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("OWNER_ID", "")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN secret is missing")
    s = st.load()
    tg = Telegram(token)
    bot = Bot(tg, s, cfg, owner)
    t0 = time.time()
    try:
        poll_telegram(tg, bot, s)
        process_kaggle(tg, bot, s, cfg)
        process_payments(bot, s, cfg)
        # keep the bot responsive until the next scheduled tick
        while time.time() - t0 < LOOP_SECONDS:
            poll_telegram(tg, bot, s)
            time.sleep(4)
        process_payments(bot, s, cfg)
        start_idle_runs(tg, bot, s, cfg)
    finally:
        s["heartbeat"] = dt.date.today().isoformat()
        changed = st.save(s)
        log("state changed" if changed else "state unchanged")


def start_idle_runs(tg, bot, s, cfg):
    """Orders placed during this tick should not wait for the next one."""
    if not any(o["status"] == "queued" for o in s["orders"].values()):
        return
    for a in accounts():
        run = s["kaggle_runs"].get(a["username"])
        if run and run.get("status") == "running":
            continue
        acc = Account(a["username"], a["key"], cfg["kaggle"]["kernel_slug"])
        try:
            start_run(acc, bot, s, cfg)
        except Exception as e:  # noqa: BLE001
            log("start run failed:", type(e).__name__, str(e)[:200])
        finally:
            acc.close()


if __name__ == "__main__":
    main()
