#!/usr/bin/env bash
set -e

SCRIPT_DIR="/home/playbit/.opencode/skills/task-management"
CLI_SCRIPT="$SCRIPT_DIR/scripts/task-cli.ts"

if [ ! -f "$CLI_SCRIPT" ]; then
    echo "Error: task-cli.ts not found at $CLI_SCRIPT"
    exit 1
fi

cd /home/playbit/Playbit/schoolcare-v2
npx tsx "$CLI_SCRIPT" "$@"
