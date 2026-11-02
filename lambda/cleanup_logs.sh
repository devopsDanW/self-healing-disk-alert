#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-}"
BIG_SIZE="${BIG_SIZE:-10M}"
KEEP_DAYS="${KEEP_DAYS:-14}"
MODE="dry-run"
[[ "${1:-}" == "--apply" ]] && MODE="apply"

case "$LOG_DIR" in
    "" | "/" | "/var" | "/var/log" | "/home" | "/etc")
    echo "ERROR: refusing to operate on LOG_DIR='$LOG_DIR'" >&2
    exit 2
    ;;
esac

if [[ ! -d "$LOG_DIR" ]]; then
    echo "ERROR: LOG_DIR '$LOG_DIR' does not exist" >&2
    exit 2
fi

BEFORE=$(df --output=pcent "$LOG_DIR" | tail -n1 | tr -dc '0-9')

TRUNCATED=0
while IFS= read -r -d '' f; do
    if [[ "$MODE" == "apply" ]]; then
        : > "$f"
    fi
    echo "TRUNCATE $f"
    TRUNCATED=$((TRUNCATED +1))
done < <(find "$LOG_DIR" -xdev -type f -name '*.log' -size +"$BIG_SIZE" -print0)

DELETED=0
while IFS= read -r -d '' f; do
    if [[ "$MODE" == "apply" ]]; then
        rm -f "$f"
    fi
    echo "DELETE $f"
    DELETED=$((DELETED+1))
done < <(find "$LOG_DIR" -xdev -type f -name '*.gz' -mtime +"$KEEP_DAYS" -print0)

AFTER=$(df --output=pcent "$LOG_DIR" | tail -n1 | tr -dc '0-9')

echo "MODE=$MODE"
echo "BEFORE=${BEFORE}%"
echo "AFTER=${AFTER}%"
echo "SUMMARY truncated=$TRUNCATED deleted=$DELETED mode=$MODE"

