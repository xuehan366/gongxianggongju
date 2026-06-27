#!/bin/bash
# 局域网文件共享工具 - macOS/Linux 启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -eq 0 ]; then
    python3 "$SCRIPT_DIR/lan_share.py"
else
    python3 "$SCRIPT_DIR/lan_share.py" "$1"
fi
