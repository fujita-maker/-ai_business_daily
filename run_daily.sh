#!/bin/bash
# cronから呼び出すためのラッパースクリプト。
# cronはPATHや作業ディレクトリが最小限しか設定されないため、
# ここで明示的にディレクトリ移動とPython実行パスの指定を行う。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 仮想環境を使っている場合はここを venv/bin/python3 等に変更してください
PYTHON_BIN="python3"

"$PYTHON_BIN" daily_report.py >> "$SCRIPT_DIR/logs/cron_stdout.log" 2>&1
