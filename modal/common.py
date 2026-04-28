"""Shared Modal definitions for the workflow-induction-toolkit cloud setup.

Every Modal app (`llm_server.py`, `pipeline.py`, `upload.py`, `download.py`)
imports the volumes, images, and defaults defined here so the pieces stay
in sync.
"""
import pathlib

import modal

# --- Naming -----------------------------------------------------------------

APP_PREFIX = "workflow-induction"

# --- Model defaults (override via CLI flags or environment) -----------------

DEFAULT_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
DEFAULT_GPU = "A10G"  # 24 GB; Qwen2.5-VL-7B fits with headroom
MAX_MODEL_LEN = 32768
LIMIT_MM_PER_PROMPT_IMAGE = 10  # annotate_high_level_nodes packs up to 10 images/call

# --- Volumes ----------------------------------------------------------------

# Recordings (input) and workflow.json/txt (output) live here.
data_volume = modal.Volume.from_name(
    f"{APP_PREFIX}-data", create_if_missing=True
)
DATA_VOLUME_PATH = "/data"

# HuggingFace cache so the LLM weights aren't re-downloaded on every cold start.
hf_cache_volume = modal.Volume.from_name(
    f"{APP_PREFIX}-hf-cache", create_if_missing=True
)
HF_CACHE_PATH = "/root/.cache/huggingface"

# --- Paths ------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
WORKFLOW_INDUCTION_DIR = REPO_ROOT / "workflow-induction"
REMOTE_WORKFLOW_INDUCTION_DIR = "/root/workflow-induction"

# --- Images -----------------------------------------------------------------

# CPU-only image for the orchestration pipeline. Bakes in the workflow-induction
# source tree so subprocess calls find the scripts at a stable path.
pipeline_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "pandas",
        "numpy",
        "opencv-python-headless",
        "sqlalchemy",
        "openai>=1.30",
    )
    .add_local_dir(
        local_path=str(WORKFLOW_INDUCTION_DIR),
        remote_path=REMOTE_WORKFLOW_INDUCTION_DIR,
        copy=True,
    )
)

# GPU image for vLLM. Pinned to a known-good vLLM release; bump as needed.
vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.7.3",
        "qwen-vl-utils[decord]",
        "huggingface_hub",
        "hf_transfer",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        }
    )
)
