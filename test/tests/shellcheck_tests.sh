#!/usr/bin/env bash

THIS_DIR=$(readlink -f "$(dirname "${BASH_SOURCE[0]}")")
REPO_ROOT=$(dirname "$THIS_DIR")
PAV_PATH="$REPO_ROOT/bin/pav"

# Test Pavilion entrypoint script
shellcheck "$PAV_PATH"

# Test cd script
CD_PATH="$REPO_ROOT/lib/pavilion/commands/ch.sh"
shellcheck "$CD_PATH"

# Test generated activate.sh script
temp_dir=$(mktemp -d)
cd "$temp_dir"
touch pavilion.yaml
export PAV_CONFIG_DIR="$THIS_DIR"
"$PAV_PATH" make-activate
shellcheck activate.sh