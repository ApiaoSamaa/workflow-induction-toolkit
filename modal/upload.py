"""Upload a local recording directory to the Modal data volume.

The recording dir is whatever `crec` produced under ~/Downloads/ — it must
contain a `records/` subdirectory with `actions.db` and `screenshots/`.

Usage
-----
    python modal/upload.py \\
        --local ~/Downloads/2026-04-27_my_recording \\
        --remote my_recording

After upload, the recording lives at /my_recording/ on the volume; pass
`--recording-subdir my_recording` to `pipeline.py`.
"""
import argparse
import os
import sys

from common import APP_PREFIX, data_volume


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--local",
        required=True,
        help="Local recording directory (must contain records/).",
    )
    parser.add_argument(
        "--remote",
        required=True,
        help="Subdirectory name on the data volume.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files on the volume.",
    )
    args = parser.parse_args()

    local_path = os.path.abspath(os.path.expanduser(args.local))
    if not os.path.isdir(os.path.join(local_path, "records")):
        sys.exit(
            f"error: {local_path}/records/ not found. "
            f"Pass the parent directory that contains `records/`."
        )

    remote_path = f"/{args.remote.strip('/')}"
    print(f"Uploading {local_path} → volume://{APP_PREFIX}-data{remote_path}/ ...")

    with data_volume.batch_upload(force=args.force) as batch:
        batch.put_directory(local_path, remote_path)

    print("Upload complete.")
    print()
    print("Run the pipeline with:")
    print(
        f"  modal run modal/pipeline.py "
        f"--recording-subdir {args.remote} --base-url <LLM_URL>"
    )


if __name__ == "__main__":
    main()
