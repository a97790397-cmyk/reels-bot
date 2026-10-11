# ReelsArabi - generation script that runs on Kaggle (GPU).
# The orchestrator fills in JOBS_B64 and SETTINGS_B64 before pushing.
# Output: /kaggle/working/out/<job_id>/scene_<i>.mp4 + plan.json, and out/results.json

import base64, gc, json, os, random, re, subprocess, sys, time, traceback

JOBS = json.loads(base64.b64decode("__JOBS_B64__").decode("utf-8"))
SETTINGS = json.loads(base64.b64decode("__SETTINGS_B64__").decode("utf-8"))

OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
RESULTS_PATH = os.path.join(OUT, "results.json")
results = {}
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.0f}s]", *a, flush=True)


def save_results():
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


log("installing packages")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "-U",
     "diffusers>=0.33.0", "transformers>=4.49.0", "accelerate>=1.2.0",
     "bitsandbytes>=0.45.0", "ftfy", "imageio", "imageio-ffmpeg", "sentencepiece"],
    check=False,
)

import torch  # noqa: E402

GPU_OK = torch.cuda.is_available()
log("cuda:", GPU_OK, torch.cuda.get_device_name(0) if GPU_OK else "-")
DTYPE = torch.bfloat16 if (GPU_OK and torch.cuda.is_bf16_supported()) else torch.float16


def free_memory():
    gc.collect()
    if GPU_OK:
        torch.cuda.empty_cache()


# ---------------------------------------------------------------- 1) planning
LANG_NAMES = {"ar": "Arabic (simple, catchy, Gulf-friendly Modern Standard Arabic)", "en": "English"}

PLAN_SYSTEM = (
    "You are a senior performance-marketing creative director who writes short vertical video ads "
    "(TikTok / Instagram Reels). You turn a product description into a scene-by-scene plan. "
    "Reply with ONLY valid JSON, no markdown."
)


def plan_prompt(job):
    n = job["scenes"]
    lang = LANG_NAMES.get(job["lang"], "English")
    parts = [
        f"Product description from the client:\n\"\"\"{job['desc']}\"\"\"\n",
        f"Write a {n}-scene vertical video ad. Each scene is a 5-second AI-generated video clip.",
        "Rules:",
        "- Scene 1 is a strong visual hook. The last scene builds desire for the product.",
        "- 'visual' is an English prompt for a text-to-video model: one concrete shot, subject, action, setting, "
        "lighting, camera movement, cinematic, photorealistic, vertical framing. Never ask for written text, logos "
        "or letters inside the video. Max 60 words.",
        f"- 'caption' is the on-screen text for that scene in {lang}. Max 7 words. Persuasive, no hashtags.",
        f"- 'cta' is a short call to action in {lang} (max 6 words), include the price or offer if the client gave one.",
        'JSON format: {"scenes":[{"visual":"...","caption":"..."}],"cta":"..."}',
    ]
    if job.get("mode") == "edit" and job.get("prev_plan"):
        parts.append("\nThis is a REVISION. Previous plan:\n" + json.dumps(job["prev_plan"], ensure_ascii=False))
        parts.append("Client's requested changes (apply them, keep what they did not mention):\n" + job.get("feedback", ""))
    elif job.get("mode") == "regen":
        parts.append("\nThe client asked for a completely fresh version. Use new ideas and new visuals.")
    return "\n".join(parts)


def parse_plan(text, job):
    try:
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0))
        scenes = [s for s in data.get("scenes", []) if s.get("visual")]
        if not scenes:
            raise ValueError("no scenes")
        n = job["scenes"]
        while len(scenes) < n:
            scenes.append(scenes[len(scenes) % len(scenes)])
        scenes = scenes[:n]
        return {"scenes": [{"visual": s["visual"][:600], "caption": str(s.get("caption", ""))[:80]} for s in scenes],
                "cta": str(data.get("cta", ""))[:80]}
    except Exception as e:  # noqa: BLE001
        log("plan parse failed, using fallback:", e)
        return fallback_plan(job)


def fallback_plan(job):
    shots = [
        "close-up product shot on a clean marble surface, soft studio lighting, slow camera push-in, cinematic, photorealistic",
        "happy person using the product in a bright modern home, natural light, handheld camera, photorealistic",
        "elegant slow-motion detail shot with bokeh lights in the background, premium commercial look",
        "lifestyle shot outdoors at golden hour, smiling customer, smooth gimbal movement, photorealistic",
        "product rotating slowly on a pedestal with dramatic rim light, dark background, luxury commercial",
        "fast dynamic montage feeling, colorful background, energetic commercial style, photorealistic",
    ]
    caps_ar = ["لا تفوّت هذا!", "جودة تستاهل", "تفاصيل تفرق", "جربه اليوم", "الكل يسأل عنه", "اطلبه الآن"]
    caps_en = ["Don't miss this!", "Quality you can feel", "Details that matter", "Try it today", "Everyone's asking", "Order now"]
    caps = caps_ar if job["lang"] == "ar" else caps_en
    hint = re.sub(r"\s+", " ", job["desc"])[:120]
    scenes = [{"visual": f"{shots[i % len(shots)]}, featuring: {hint}", "caption": caps[i % len(caps)]}
              for i in range(job["scenes"])]
    return {"scenes": scenes, "cta": "اطلب الآن" if job["lang"] == "ar" else "Order now"}


def make_plans(jobs):
    need = [j for j in jobs if not j.get("plan")]
    if not need:
        return
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        mid = SETTINGS.get("llm", "Qwen/Qwen2.5-7B-Instruct")
        log("loading planner", mid)
        tok = AutoTokenizer.from_pretrained(mid)
        model = AutoModelForCausalLM.from_pretrained(
            mid, device_map="auto",
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                                                   bnb_4bit_quant_type="nf4"),
        )
        for job in need:
            msgs = [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": plan_prompt(job)}]
            ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(model.device)
            out = model.generate(ids, max_new_tokens=900, do_sample=True, temperature=0.8, top_p=0.9)
            text = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
            job["plan"] = parse_plan(text, job)
            log("planned", job["job_id"])
        del model
    except Exception:  # noqa: BLE001
        log("planner failed, fallback plans\n" + traceback.format_exc())
        for job in need:
            if not job.get("plan"):
                job["plan"] = fallback_plan(job)
    free_memory()


# ---------------------------------------------------------------- 2) video
NEGATIVE = ("text, letters, watermark, logo, subtitles, blurry, low quality, distorted hands, extra fingers, "
            "deformed face, static frame, overexposed, jpeg artifacts, ugly, worst quality")


def load_video_pipe():
    from diffusers import AutoencoderKLWan, WanPipeline
    mid = SETTINGS.get("video_model", "Wan-AI/Wan2.1-T2V-1.3B-Diffusers")
    log("loading video model", mid, DTYPE)
    vae = AutoencoderKLWan.from_pretrained(mid, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanPipeline.from_pretrained(mid, vae=vae, torch_dtype=DTYPE)
    pipe.enable_model_cpu_offload()
    return pipe


def render_clip(pipe, prompt, path, seed):
    from diffusers.utils import export_to_video
    g = torch.Generator("cpu").manual_seed(seed)
    frames = pipe(
        prompt=prompt + ", vertical 9:16 composition, high detail, smooth motion",
        negative_prompt=NEGATIVE,
        height=832, width=480, num_frames=81,
        num_inference_steps=int(SETTINGS.get("steps", 25)),
        guidance_scale=5.0, generator=g,
    ).frames[0]
    export_to_video(frames, path, fps=16)


def main():
    log("jobs:", len(JOBS))
    make_plans(JOBS)
    for job in JOBS:
        d = os.path.join(OUT, job["job_id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(job["plan"], f, ensure_ascii=False)
        results[job["job_id"]] = {"ok": False, "plan": job["plan"], "clips": []}
    save_results()

    pipe = load_video_pipe()
    deadline = T0 + float(SETTINGS.get("time_budget_s", 8 * 3600))
    for job in JOBS:
        res = results[job["job_id"]]
        try:
            base_seed = int(job.get("seed") or random.randint(1, 10**9))
            for i, sc in enumerate(job["plan"]["scenes"]):
                if time.time() > deadline:
                    raise TimeoutError("time budget reached")
                rel = f"{job['job_id']}/scene_{i}.mp4"
                log("render", rel)
                render_clip(pipe, sc["visual"], os.path.join(OUT, rel), base_seed + i)
                res["clips"].append(rel)
                save_results()
            res["ok"] = True
        except Exception as e:  # noqa: BLE001
            res["error"] = f"{type(e).__name__}: {e}"[:500]
            log("job failed", job["job_id"], traceback.format_exc())
        save_results()
    log("done")


if __name__ == "__main__":
    main()
