"""Push generation jobs to Kaggle, poll status, download outputs (via the official kaggle CLI)."""
import base64
import json
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "kaggle_kernel", "gen_template.py")


def accounts():
    """Kaggle accounts from secrets: KAGGLE_USERNAME/KAGGLE_KEY, plus optional _2, _3 ..."""
    out = []
    for suffix in ["", "_2", "_3", "_4"]:
        u, k = os.environ.get("KAGGLE_USERNAME" + suffix), os.environ.get("KAGGLE_KEY" + suffix)
        if u and k:
            out.append({"username": u.strip(), "key": k.strip()})
    return out


class Account:
    def __init__(self, username, key, slug):
        self.username, self.key, self.slug = username, key, slug
        self.kernel = f"{username}/{slug}"
        self.cfg = tempfile.mkdtemp(prefix="kg_")
        with open(os.path.join(self.cfg, "kaggle.json"), "w") as f:
            json.dump({"username": username, "key": key}, f)
        os.chmod(os.path.join(self.cfg, "kaggle.json"), 0o600)

    def _run(self, args, timeout=600):
        env = {k: v for k, v in os.environ.items() if not k.startswith("KAGGLE_")}
        env["KAGGLE_CONFIG_DIR"] = self.cfg
        r = subprocess.run(["kaggle", *args], capture_output=True, text=True, env=env, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def push(self, jobs, settings):
        code = open(TEMPLATE, encoding="utf-8").read()
        code = code.replace("__JOBS_B64__", base64.b64encode(json.dumps(jobs, ensure_ascii=False).encode()).decode())
        code = code.replace("__SETTINGS_B64__", base64.b64encode(json.dumps(settings).encode()).decode())
        d = tempfile.mkdtemp(prefix="kpush_")
        with open(os.path.join(d, "gen.py"), "w", encoding="utf-8") as f:
            f.write(code)
        meta = {
            "id": self.kernel, "title": self.slug, "code_file": "gen.py",
            "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": True, "enable_tpu": False, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": [],
        }
        with open(os.path.join(d, "kernel-metadata.json"), "w") as f:
            json.dump(meta, f)
        args = ["kernels", "push", "-p", d]
        if settings.get("timeout_s"):
            args += ["-t", str(int(settings["timeout_s"]))]
        ok = lambda rc, out: rc == 0 and ("successfully" in out.lower() or "error" not in out.lower())
        out = ""
        if settings.get("accelerator"):
            rc, out = self._run(args + ["--accelerator", settings["accelerator"]])
            if ok(rc, out):
                shutil.rmtree(d, ignore_errors=True)
                return out
        rc, out2 = self._run(args)  # fall back to Kaggle's default GPU
        shutil.rmtree(d, ignore_errors=True)
        if not ok(rc, out2):
            raise RuntimeError("kaggle push failed: " + (out + out2)[-600:])
        return out2

    def status(self):
        """-> 'running' | 'queued' | 'complete' | 'error' | 'cancelled' | 'unknown'"""
        rc, out = self._run(["kernels", "status", self.kernel], timeout=120)
        low = out.lower()
        if "has status" not in low:
            return "unknown"  # CLI/network problem: do not treat as finished
        tail = low.split("has status", 1)[1].splitlines()[0]
        for word in ("complete", "error", "cancel", "running", "queued"):
            if word in tail:
                return "cancelled" if word == "cancel" else word
        return "unknown"

    def download(self, dest):
        os.makedirs(dest, exist_ok=True)
        rc, out = self._run(["kernels", "output", self.kernel, "-p", dest, "-o"], timeout=1200)
        if rc != 0:
            raise RuntimeError("kaggle output failed: " + out[-500:])
        return dest

    def close(self):
        shutil.rmtree(self.cfg, ignore_errors=True)
