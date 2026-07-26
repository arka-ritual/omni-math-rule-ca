#!/usr/bin/env python3
"""Serve an open-weights model on a Modal GPU as an OpenAI-compatible endpoint.

Used by the rebuttal's base-model experiment (WS3): Qwen3.5-9B-Base and
Gemma-4-31B have no hosted inference provider — the paper says as much in a
footnote — so to prompt them at all we have to stand up vLLM ourselves.

Deliberately built on `modal.Sandbox` + a TCP tunnel rather than a deployed
`@modal.web_server` app, for one reason: **explicit lifecycle**. A GPU costs
1-4 $/hour and the whole experiment budget is tens of dollars, so the code that
starts the GPU should be the code that stops it, in a `finally`. `serve()` is a
context manager that guarantees exactly that.

NOTE ON THE DIRECTORY NAME: this package is `modal_apps/`, not `modal/`. A
top-level `modal/` directory in the repo root would shadow the installed `modal`
package for anything run from the repo root.

Usage as a library (the intended path — see inference/run_zeroshot_raw.py):

    from modal_apps.vllm_sandbox import serve
    with serve("Qwen/Qwen3.5-9B-Base", gpu="L40S") as base_url:
        ...  # base_url like https://xxx.modal.host/v1

Usage as a CLI, for poking at a server by hand:

    python modal_apps/vllm_sandbox.py --model Qwen/Qwen3.5-9B-Base --gpu L40S
    python modal_apps/vllm_sandbox.py --list
    python modal_apps/vllm_sandbox.py --stop-all
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

import modal

APP_NAME = os.environ.get("MODAL_VLLM_APP_NAME", "omni-math-vllm")
VLLM_PORT = 8000

# vLLM version is pinned so a silent upstream bump can't change generation
# behaviour between runs of the same experiment.
VLLM_VERSION = os.environ.get("MODAL_VLLM_VERSION", "0.11.0")

# Weights are cached in a Volume across runs. Without this every GPU boot
# re-downloads tens of GB *while the GPU meter is running* — for Gemma-4-31B
# that is ~62 GB of download billed at GPU rates.
HF_CACHE_VOLUME = "omni-math-hf-cache"
HF_CACHE_PATH = "/root/.cache/huggingface"

# Per-model GPU sizing. bf16 weights are ~2 bytes/param, plus KV cache and
# activations; leave real headroom or vLLM fails at load with a cryptic OOM.
DEFAULT_GPU_FOR = {
    "Qwen/Qwen3.5-9B-Base": "L40S",       # ~18 GB weights, fits 48 GB with room
    "Qwen/Qwen3.5-9B": "L40S",
    "google/gemma-4-31b": "A100-80GB",    # ~62 GB weights, needs 80 GB
    "google/gemma-4-31b-it": "A100-80GB",
}


def _image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            f"vllm=={VLLM_VERSION}",
            "huggingface_hub[hf_transfer]",
        )
        # hf_transfer gives a much faster download; the flag is what actually
        # enables it. VLLM_* keep vLLM from phoning home mid-run.
        .env({
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "VLLM_DO_NOT_TRACK": "1",
            "DO_NOT_TRACK": "1",
        })
    )


def _secrets() -> list[modal.Secret]:
    """Forward HF_TOKEN from the local .env, if present."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        return []
    return [modal.Secret.from_dict({"HF_TOKEN": token, "HUGGING_FACE_HUB_TOKEN": token})]


def get_app() -> modal.App:
    return modal.App.lookup(APP_NAME, create_if_missing=True)


def prefetch(model: str, timeout: int = 3600) -> None:
    """Download a model's weights into the cache Volume on a CPU-only sandbox.

    Pulling ~62 GB inside the GPU sandbox would bill that download at GPU rates.
    Doing it here first costs cents instead. Idempotent: the second call is a
    no-op because the Volume already holds the snapshot.
    """
    app = get_app()
    volume = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
    script = (
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download({model!r}, ignore_patterns=['*.pt', '*.pth', 'original/*'])"
    )
    print(f"[vllm] prefetching {model} into volume '{HF_CACHE_VOLUME}' (CPU-only)...")
    sb = modal.Sandbox.create(
        "python", "-c", script,
        image=_image(),
        app=app,
        volumes={HF_CACHE_PATH: volume},
        secrets=_secrets(),
        timeout=timeout,
        cpu=4,
        memory=8192,
    )
    try:
        for line in sb.stdout:
            print("   ", line.rstrip())
        rc = sb.wait()
        if rc != 0:
            err = sb.stderr.read()
            raise RuntimeError(f"prefetch of {model} failed (rc={rc}):\n{err[-2000:]}")
    finally:
        with contextlib.suppress(Exception):
            sb.terminate()
    print(f"[vllm] prefetch of {model} complete.")


def _wait_healthy(base_url: str, sandbox, timeout: int) -> None:
    health = base_url.rsplit("/v1", 1)[0] + "/health"
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        if sandbox.poll() is not None:
            raise RuntimeError(
                f"vLLM sandbox exited before becoming healthy:\n{sandbox.stderr.read()[-3000:]}"
            )
        try:
            with urllib.request.urlopen(health, timeout=10) as r:
                if r.status == 200:
                    return
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(10)
    raise TimeoutError(f"vLLM did not become healthy within {timeout}s (last: {last})")


@contextlib.contextmanager
def serve(
    model: str,
    *,
    gpu: str | None = None,
    max_model_len: int = 8192,
    lifetime: int = 7200,
    idle_timeout: int = 900,
    boot_timeout: int = 1800,
    extra_args: list[str] | None = None,
):
    """Start vLLM on a Modal GPU, yield its `/v1` base URL, always shut it down.

    The `finally` is the point of this function. A GPU sandbox left running
    bills continuously; every exit path — success, exception, Ctrl-C — goes
    through terminate. `lifetime` and `idle_timeout` are server-side backstops
    for the case where this process dies without unwinding.
    """
    gpu = gpu or DEFAULT_GPU_FOR.get(model, "A100-80GB")
    app = get_app()
    volume = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)

    args = [
        "vllm", "serve", model,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--max-model-len", str(max_model_len),
        "--gpu-memory-utilization", "0.92",
        # Serving a base model: no chat template exists, and inference_api.py's
        # --base_model path uses /v1/completions anyway.
        "--disable-log-requests",
        *(extra_args or []),
    ]

    print(f"[vllm] starting {model} on {gpu} (max_model_len={max_model_len})...")
    sandbox = modal.Sandbox.create(
        *args,
        image=_image(),
        app=app,
        gpu=gpu,
        volumes={HF_CACHE_PATH: volume},
        secrets=_secrets(),
        timeout=lifetime,
        idle_timeout=idle_timeout,
        encrypted_ports=[VLLM_PORT],
        cpu=4,
        memory=16384,
    )
    try:
        tunnel = sandbox.tunnels()[VLLM_PORT]
        base_url = f"{tunnel.url}/v1"
        print(f"[vllm] sandbox {sandbox.object_id}, url {base_url}")
        print(f"[vllm] waiting for health (up to {boot_timeout}s)...")
        _wait_healthy(base_url, sandbox, boot_timeout)
        print(f"[vllm] {model} is serving.")
        yield base_url
    finally:
        print(f"[vllm] terminating sandbox {sandbox.object_id}")
        with contextlib.suppress(Exception):
            sandbox.terminate()


def list_sandboxes() -> list:
    app = get_app()
    return [sb for sb in modal.Sandbox.list(app_id=app.app_id) if sb.poll() is None]


def stop_all() -> list[str]:
    ids = []
    for sb in list_sandboxes():
        ids.append(sb.object_id)
        with contextlib.suppress(Exception):
            sb.terminate()
    return ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--gpu", default=None)
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--prefetch-only", action="store_true",
                    help="Download weights into the cache Volume and exit (CPU-only, cheap).")
    ap.add_argument("--hold", type=int, default=0,
                    help="Seconds to keep the server up after it is healthy (CLI poking).")
    ap.add_argument("--list", action="store_true", help="List live sandboxes in the app.")
    ap.add_argument("--stop-all", action="store_true", help="Terminate every live sandbox.")
    args = ap.parse_args()

    if args.list:
        live = list_sandboxes()
        print(f"{len(live)} live sandbox(es) in '{APP_NAME}':")
        for sb in live:
            print(" ", sb.object_id)
        return 0

    if args.stop_all:
        killed = stop_all()
        print(f"terminated {len(killed)}: {killed}")
        return 0

    if not args.model:
        ap.error("--model is required (or use --list / --stop-all)")

    if args.prefetch_only:
        prefetch(args.model)
        return 0

    with serve(args.model, gpu=args.gpu, max_model_len=args.max_model_len) as base_url:
        print(f"\nbase_url = {base_url}")
        try:
            with urllib.request.urlopen(f"{base_url}/models", timeout=30) as r:
                print("models:", json.dumps(json.load(r), indent=2)[:500])
        except urllib.error.URLError as e:
            print("could not list models:", e)
        if args.hold:
            print(f"holding for {args.hold}s...")
            time.sleep(args.hold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
