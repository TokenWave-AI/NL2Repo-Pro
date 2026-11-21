#!/usr/bin/env bash
# Download NL2Repo-Pro tasks from Hugging Face, verify them, unpack them and load their images.
#
#   scripts/fetch.sh all                      every task (4.3 GB of tasks, 83 GB of images)
#   scripts/fetch.sh python                   one language: python, go, rust, java or javascript
#   scripts/fetch.sh <instance_id> [...]      named tasks
#
# Tasks are unpacked to $DATA_DIR/run/<instance_id>. Set DATA_DIR to change the place
# (default ./NL2Repo-Pro) and DROP_IMAGE_TARS=1 to delete each image archive once it is loaded.
set -euo pipefail

REPO=Tokenwave-AI/NL2Repo-Pro
REVISION=v1.0
DATA_DIR=${DATA_DIR:-NL2Repo-Pro}
HERE=$(cd "$(dirname "$0")/.." && pwd)
LANGS="python go rust java javascript"

[ $# -ge 1 ] || { sed -n '2,9p' "$0"; exit 1; }

includes=(--include SHA256SUMS)
for arg in "$@"; do
  if [ "$arg" = all ]; then
    includes+=(--include "tasks/*" --include "images/*")
  elif [[ " $LANGS " == *" $arg "* ]]; then
    includes+=(--include "tasks/$arg/*" --include "images/$arg/*")
  else
    lang=$(awk -F'\t' -v id="$arg" '$1 == id {print $2; exit}' "$HERE/results/paper-v1.tsv")
    [ -n "$lang" ] || { echo "unknown task: $arg" >&2; exit 1; }
    includes+=(--include "tasks/$lang/$arg.tar.zst" --include "images/$lang/$arg.tar")
  fi
done

hf download "$REPO" --repo-type dataset --revision "$REVISION" --local-dir "$DATA_DIR" "${includes[@]}"

cd "$DATA_DIR"
sha256sum -c SHA256SUMS --ignore-missing --quiet
mkdir -p run
shopt -s nullglob
for archive in tasks/*/*.tar.zst; do
  id=$(basename "$archive" .tar.zst)
  [ -d "run/$id" ] || tar -I zstd -xf "$archive" -C run
done
for archive in images/*/*.tar; do
  id=$(basename "$archive" .tar)
  images=$(grep -h '^docker_image' "run/$id/task.toml" | cut -d'"' -f2)
  loaded=1
  for image in $images; do docker image inspect "$image" >/dev/null 2>&1 || loaded=0; done
  [ "$loaded" = 1 ] || docker load -q -i "$archive"
  [ "${DROP_IMAGE_TARS:-0}" = 1 ] && rm -f "$archive"
done
echo "tasks ready in $DATA_DIR/run: $(ls run | wc -l)"
