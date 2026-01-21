#!/bin/sh
set -eu

heartbeat_file="/data/heartbeat"

if [ ! -s "$heartbeat_file" ]; then exit 1; fi

next_run_raw=$(head -n 1 "$heartbeat_file" | tr -d '\r\n')
if [ -z "$next_run_raw" ]; then exit 1; fi

next_run_ts=$(date -u -d "$next_run_raw" +%s 2>/dev/null || :)
if [ -z "$next_run_ts" ]; then exit 1; fi

now_ts=$(date -u +%s)
allowed_ts=$((next_run_ts + 59))

if [ "$now_ts" -le "$allowed_ts" ]; then exit 0; fi

exit 1
