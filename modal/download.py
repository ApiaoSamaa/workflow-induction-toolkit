"""Download workflow outputs from the Modal data volume to your laptop.

Usage
-----
    python modal/download.py \\
        --remote my_recording \\
        --local ./outputs/my_recording

By default, pulls workflow.json and workflow.txt. Pass --files to override.
"""
import argparse
import os
import sys

from common import APP_PREFIX, data_volume

DEFAULT_FILES = ["workflow.json", "workflow.txt"]


def download_one(remote_path: str, local_path: str) -> bool:
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    try:
        with open(local_path, "wb") as f:
            for chunk in data_volume.read_file(remote_path):
                f.write(chunk)
    except FileNotFoundError:
        print(f"  [skip] {remote_path} not found on volume")
        return False
    print(f"  {remote_path} → {local_path}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--remote",
        required=True,
        help="Subdirectory on the data volume holding outputs.",
    )
    parser.add_argument(
        "--local",
        required=True,
        help="Local destination directory.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=DEFAULT_FILES,
        help=f"Filenames to fetch from the remote subdir (default: {DEFAULT_FILES}).",
    )
    args = parser.parse_args()

    remote_dir = f"/{args.remote.strip('/')}"
    local_dir = os.path.abspath(os.path.expanduser(args.local))
    print(f"Downloading from volume://{APP_PREFIX}-data{remote_dir}/ → {local_dir}/")

    any_ok = False
    for name in args.files:
        ok = download_one(
            remote_path=f"{remote_dir}/{name}",
            local_path=os.path.join(local_dir, name),
        )
        any_ok = any_ok or ok

    if not any_ok:
        sys.exit(
            "Nothing was downloaded. Did the pipeline finish? "
            f"Try: modal volume ls {APP_PREFIX}-data {remote_dir}"
        )


if __name__ == "__main__":
    main()
