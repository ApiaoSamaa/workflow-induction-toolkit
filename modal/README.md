# Modal cloud setup for workflow-induction-toolkit

Run the induction pipeline on [Modal](https://modal.com/) when you don't
have a local GPU or you want to scale beyond a single recording.

## Architecture

| Piece                | Where it runs              | Lifecycle                                |
|----------------------|----------------------------|------------------------------------------|
| `llm_server.py`      | GPU container (vLLM)       | Deployed once; scales to zero when idle  |
| `pipeline.py`        | CPU container              | Spawned per pipeline run                 |
| `upload.py` / `download.py` | Your laptop         | One-shot helpers                         |
| `workflow-induction-data` (volume) | Persistent storage | Recordings + workflow.json/.txt   |
| `workflow-induction-hf-cache` (volume) | Persistent storage | HF model weights (~14 GB for Qwen2.5-VL-7B) |

The pipeline calls the LLM via `OPENAI_BASE_URL` — exactly the swap path
wired up in `workflow-induction/utils.py`. No code changes to the
induction scripts themselves.

## Prerequisites

```bash
pip install modal
modal token new   # one-time auth
```

## Step 0 (one-time): pre-cache model weights

Optional but recommended — avoids a 14 GB download blocking the first
`serve` cold start.

```bash
modal run modal/llm_server.py::download
```

To use a different model, pass `--model-name`. Examples:

```bash
modal run modal/llm_server.py::download --model-name Qwen/Qwen2.5-VL-32B-Instruct
```

## Step 1 (one-time): deploy the LLM server

```bash
modal deploy modal/llm_server.py
```

Modal prints a URL like:

```
https://<your-org>--workflow-induction-llm-serve.modal.run
```

Save it — you'll pass it as `--base-url` (with `/v1` appended) to every
pipeline run. The server scales to zero after 10 min idle and warms back
up on the next request (~30-60s once weights are cached).

To switch models or GPUs, edit `common.py` (`DEFAULT_MODEL`, `DEFAULT_GPU`)
and re-deploy.

## Step 2: upload a recording

After running `crec` on your Mac, the recording is at
`~/Downloads/<recording_dir>/records/{actions.db, screenshots/}`.

```bash
python modal/upload.py \
    --local ~/Downloads/<recording_dir> \
    --remote <recording_name>
```

`<recording_name>` is the subdirectory name on the volume — pick something
short, e.g. `gsheet_attendance`.

## Step 3: run the pipeline

```bash
modal run modal/pipeline.py \
    --recording-subdir <recording_name> \
    --base-url https://<your-org>--workflow-induction-llm-serve.modal.run/v1
```

This runs `get_human_trajectory.py → segment.py → induce.py --auto` in
sequence inside one Modal container, with `OPENAI_BASE_URL` /
`OPENAI_MODEL` set so all `call_llm` sites hit your deployed Qwen.

## Step 4: pull results back

```bash
python modal/download.py \
    --remote <recording_name> \
    --local ./outputs/<recording_name>
```

Or directly via the Modal CLI:

```bash
modal volume get workflow-induction-data \
    /<recording_name>/workflow.json ./outputs/<recording_name>/
```

## Using OpenAI instead of Qwen

If you have an OpenAI key (e.g. shared lab key) and want to A/B against
the cloud model, skip Steps 0-1 and pass:

```bash
modal run modal/pipeline.py \
    --recording-subdir <recording_name> \
    --base-url https://api.openai.com/v1 \
    --model-name gpt-4o \
    --api-key $OPENAI_API_KEY
```

## Cost notes

- A10G GPU container: ~$1.10/hr while serving, $0/hr while scaled down.
  A 5-minute pipeline run typically incurs <$0.20 of GPU time.
- CPU pipeline container: pennies per run.
- Volume storage: ~$0.20/GB-month; recordings are usually 50-500 MB,
  the HF cache is ~14 GB.

## Troubleshooting

**`vllm serve` cold start times out.** Bump `startup_timeout` in
`llm_server.py:@modal.web_server(...)`, or run `download` first to cache
weights.

**Pipeline fails with `Expected /data/<name>/records to exist`.** Your
upload didn't include the `records/` subdir. Re-upload pointing `--local`
at the parent directory (the one that *contains* `records/`).

**`induce.py` hangs on stdin.** The pipeline pipes `y\n` to handle
[induce.py:119](../workflow-induction/induce.py#L119)'s interactive
prompt. If a future change adds more `input()` calls, increase the
`auto_y` buffer length in `pipeline.py`.

**Want to keep the GPU warm.** Set `min_containers=1` on the `serve`
function in `llm_server.py` — costs ~$26/day on A10G but eliminates cold
starts.

## File map

```
modal/
├── README.md          # this file
├── common.py          # shared App prefix, volumes, images, paths
├── llm_server.py      # vLLM Qwen2.5-VL OpenAI-compat server (deploy once)
├── pipeline.py        # runs the induction pipeline against one recording
├── upload.py          # local recording → data volume
└── download.py        # data volume → local outputs
```
