#!/bin/bash
# Git运维工具配置文件
# 🔧 新项目迁移时需要检查的配置：
# 1. PYTHON_BIN - 虚拟环境路径
# 2. GPT_MODULE_ROOT - GPT模块位置  
# 3. PROMPT_DIR - prompt文件目录
# 其他配置通常不需要修改

# 项目根路径（通常不需要改）
PROJECT_ROOT="$(git rev-parse --show-toplevel)"

# Python环境（根据项目调整）
PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
PYTHON_FALLBACK="python3"

# GPT模块路径（根据项目结构调整）
GPT_MODULE_ROOT="${PROJECT_ROOT}"

# Prompt文件目录（根据项目调整）
PROMPT_DIR="${PROJECT_ROOT}/ops/gpt/prompt"

# 日志目录（通常不需要改）
LOGS_DIR="${PROJECT_ROOT}/ops/git/logs"
SNAPSHOTS_DIR="${LOGS_DIR}/snapshots"
PUSHLOGS_DIR="${LOGS_DIR}/pushlogs"

# 导出环境变量供Python脚本使用
export GPT_MODULE_ROOT
export PROMPT_DIR
export LOGS_DIR
