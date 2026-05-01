#!/bin/bash
# Clone (or update) the official SWE-bench Pro evaluation repo into
# swebench_pro/external/SWE-bench_Pro-os. We need this repo at runtime
# because the official `swe_bench_pro_eval.py` reads:
#   - dockerfiles/{base,instance}_dockerfile/<iid>/Dockerfile  (relative to cwd)
#   - run_scripts/<iid>/{run_script.sh, parser.py}             (via --scripts_dir)
#   - helper_code/image_uri.py                                  (Python import)
# So everything must be run with `cd swebench_pro/external/SWE-bench_Pro-os`.
#
# Usage:  bash swebench_pro/scripts/setup_eval_repo.sh [--update]

set -euo pipefail

REPO_URL="${SWEBENCH_PRO_REPO_URL:-https://github.com/scaleapi/SWE-bench_Pro-os.git}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DEST="$ROOT/external/SWE-bench_Pro-os"

UPDATE=0
if [ "${1:-}" = "--update" ]; then
    UPDATE=1
fi

if [ ! -d "$DEST/.git" ]; then
    mkdir -p "$ROOT/external"
    echo "[setup] Cloning $REPO_URL -> $DEST"
    git clone --depth 1 "$REPO_URL" "$DEST"
elif [ "$UPDATE" -eq 1 ]; then
    echo "[setup] Updating $DEST"
    git -C "$DEST" fetch --depth 1 origin
    git -C "$DEST" reset --hard origin/HEAD
else
    echo "[setup] $DEST already present (pass --update to refresh)"
fi

# Sanity: required files exist.
for f in swe_bench_pro_eval.py helper_code/sweap_eval_full_v2.jsonl helper_code/image_uri.py run_scripts dockerfiles; do
    if [ ! -e "$DEST/$f" ]; then
        echo "[setup] ERROR: missing $DEST/$f" >&2
        exit 1
    fi
done

echo "[setup] OK: $DEST"
