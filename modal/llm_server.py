"""vLLM Qwen2.5-VL OpenAI-compatible server, deployed on Modal.

One-time setup
--------------
    # (optional) pre-cache model weights to the HF volume so the first
    # cold start of `serve` doesn't time out on a 14 GB download:
    modal run modal/llm_server.py::download

Deploy
------
    modal deploy modal/llm_server.py

Modal will print a URL like
    https://<org>--workflow-induction-llm-serve.modal.run
Pass it to pipeline runs as `--base-url`.

Notes
-----
- The server scales to zero after `scaledown_window` seconds of idle, then
  cold-starts on the next request (~30-60s once weights are cached).
- Set `min_containers=1` to keep one warm permanently (costs ~$1/hr on A10G).
"""
import modal

from common import (
    APP_PREFIX,
    DEFAULT_GPU,
    DEFAULT_MODEL,
    HF_CACHE_PATH,
    LIMIT_MM_PER_PROMPT_IMAGE,
    MAX_MODEL_LEN,
    hf_cache_volume,
    vllm_image,
)

app = modal.App(f"{APP_PREFIX}-llm")


@app.function(
    image=vllm_image,
    gpu=DEFAULT_GPU,
    volumes={HF_CACHE_PATH: hf_cache_volume},
    timeout=24 * 3600,
    scaledown_window=600,
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=8000, startup_timeout=900)
def serve():
    """Spawn `vllm serve` and let Modal proxy traffic to port 8000."""
    import os
    import subprocess

    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    cmd = [
        "vllm",
        "serve",
        model,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--limit-mm-per-prompt",
        f"image={LIMIT_MM_PER_PROMPT_IMAGE}",
        "--gpu-memory-utilization",
        "0.90",
        "--dtype",
        "bfloat16",
    ]
    print("Starting:", " ".join(cmd))
    subprocess.Popen(cmd)


@app.function(
    image=vllm_image,
    volumes={HF_CACHE_PATH: hf_cache_volume},
    timeout=3600,
)
def _download_model_remote(model_name: str):
    from huggingface_hub import snapshot_download

    print(f"Downloading {model_name} to {HF_CACHE_PATH} ...")
    snapshot_download(model_name, local_dir_use_symlinks=False)
    hf_cache_volume.commit()
    print("Done; weights persisted to the HF cache volume.")


@app.local_entrypoint()
def download(model_name: str = DEFAULT_MODEL):
    """Pre-cache model weights so `serve` cold-starts quickly.

    Usage:
        modal run modal/llm_server.py::download
        modal run modal/llm_server.py::download --model-name Qwen/Qwen2.5-VL-32B-Instruct
    """
    _download_model_remote.remote(model_name)
