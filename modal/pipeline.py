"""Run the workflow-induction pipeline against an uploaded recording on Modal.

Prerequisites
-------------
1. `modal deploy modal/llm_server.py` — note the printed URL.
2. `python modal/upload.py --local <local_recording_dir> --remote <name>`
   to push the recording into the data volume.

Run
---
    modal run modal/pipeline.py \\
        --recording-subdir <name> \\
        --base-url https://<org>--workflow-induction-llm-serve.modal.run/v1

Outputs are written to the data volume at /<name>/workflow.json and
/<name>/workflow.txt; pull them back with `modal/download.py`.
"""
import modal

from common import (
    APP_PREFIX,
    DATA_VOLUME_PATH,
    DEFAULT_MODEL,
    REMOTE_WORKFLOW_INDUCTION_DIR,
    data_volume,
    pipeline_image,
)

app = modal.App(f"{APP_PREFIX}-pipeline")


@app.function(
    image=pipeline_image,
    volumes={DATA_VOLUME_PATH: data_volume},
    timeout=2 * 3600,
)
def run_pipeline(
    recording_subdir: str,
    base_url: str,
    model_name: str = DEFAULT_MODEL,
    api_key: str = "EMPTY",
) -> dict:
    """Run get_human_trajectory → segment → induce on one recording dir.

    The recording must already be uploaded to the data volume at
    /<recording_subdir>/records/{actions.db, screenshots/}.
    """
    import os
    import subprocess

    data_dir = os.path.join(DATA_VOLUME_PATH, recording_subdir)
    records_dir = os.path.join(data_dir, "records")
    if not os.path.isdir(records_dir):
        raise FileNotFoundError(
            f"Expected {records_dir} to exist. "
            f"Upload your recording first with modal/upload.py."
        )

    # Make sure the volume reflects the latest uploaded state.
    data_volume.reload()

    env = {
        **os.environ,
        "OPENAI_BASE_URL": base_url,
        "OPENAI_MODEL": model_name,
        "OPENAI_API_KEY": api_key,
    }
    cwd = REMOTE_WORKFLOW_INDUCTION_DIR

    # induce.py blocks on a `final = input(...)` prompt even in --auto mode
    # ([induce.py:119]). Pipe a stream of "y\n" so the subprocess proceeds.
    auto_y = ("y\n" * 64).encode()

    print(f"[1/3] get_human_trajectory.py --data_dir {data_dir}")
    subprocess.run(
        ["python", "get_human_trajectory.py", "--data_dir", data_dir],
        cwd=cwd,
        env=env,
        check=True,
    )

    print(f"[2/3] segment.py --data_dir {data_dir}")
    subprocess.run(
        ["python", "segment.py", "--data_dir", data_dir],
        cwd=cwd,
        env=env,
        check=True,
        input=auto_y,
    )

    print(f"[3/3] induce.py --data_dir {data_dir} --auto")
    subprocess.run(
        ["python", "induce.py", "--data_dir", data_dir, "--auto"],
        cwd=cwd,
        env=env,
        check=True,
        input=auto_y,
    )

    # Persist outputs so other functions / `modal volume get` see them.
    data_volume.commit()

    workflow_json = os.path.join(data_dir, "workflow.json")
    workflow_txt = os.path.join(data_dir, "workflow.txt")
    return {
        "workflow_json": workflow_json,
        "workflow_txt": workflow_txt,
        "json_exists": os.path.exists(workflow_json),
        "txt_exists": os.path.exists(workflow_txt),
    }


@app.local_entrypoint()
def main(
    recording_subdir: str,
    base_url: str,
    model_name: str = DEFAULT_MODEL,
    api_key: str = "EMPTY",
):
    """Drive the pipeline from your laptop.

    Args:
        recording_subdir: name under the data volume holding `records/`.
        base_url: deployed LLM server URL, ending in /v1
                  (e.g. https://<org>--workflow-induction-llm-serve.modal.run/v1).
        model_name: model identifier the LLM server is serving.
        api_key: pass a real key if base_url points at OpenAI; "EMPTY" works
                 for self-hosted vLLM.
    """
    result = run_pipeline.remote(
        recording_subdir=recording_subdir,
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
    )
    print("\nPipeline finished:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("\nDownload outputs with:")
    print(
        f"  python modal/download.py --remote {recording_subdir} "
        f"--local ./outputs/{recording_subdir}"
    )
