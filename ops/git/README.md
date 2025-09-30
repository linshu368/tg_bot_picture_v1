# Git 运维工具

这是一套完整的 Git 版本管理和 AI 总结运维工具，支持自动生成 commit 消息和 push 日志。

## 功能特性

- 🤖 **AI 自动生成 commit 消息**：基于代码差异自动生成规范的提交信息
- 📊 **智能 push 日志**：生成面向工程和产品的双重总结
- 🔄 **自动快照管理**：commit 时保存快照，push 时整理归档
- ⚙️ **配置化路径管理**：支持不同项目快速迁移部署

## 快速开始

### 当前项目安装

```bash
# 安装 git hooks
bash ops/git/install_hooks.sh
```

### 新项目迁移

1. **复制工具目录**
   ```bash
   cp -r /path/to/current/project/ops/git /path/to/new/project/ops/
   ```

2. **修改配置文件**
   编辑 `ops/git/config.sh`，调整以下配置：
   ```bash
   # Python环境路径
   PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
   
   # GPT模块路径 
   GPT_MODULE_ROOT="${PROJECT_ROOT}"
   
   # Prompt文件目录
   PROMPT_DIR="${PROJECT_ROOT}/gpt/prompt"
   ```

3. **安装到新项目**
   ```bash
   cd /path/to/new/project
   bash ops/git/install_hooks.sh
   ```

## 配置说明

### config.sh 配置文件

| 配置项 | 说明 | 默认值 | 是否需要修改 |
|--------|------|--------|-------------|
| `PROJECT_ROOT` | 项目根路径 | 自动检测 | ❌ 通常不需要 |
| `PYTHON_BIN` | Python 环境路径 | `${PROJECT_ROOT}/venv/bin/python` | ✅ 根据项目调整 |
| `GPT_MODULE_ROOT` | GPT 模块路径 | `${PROJECT_ROOT}` | ✅ 根据项目结构调整 |
| `PROMPT_DIR` | Prompt 文件目录 | `${PROJECT_ROOT}/gpt/prompt` | ✅ 根据项目调整 |
| `LOGS_DIR` | 日志存储目录 | `${PROJECT_ROOT}/ops/git/logs` | ❌ 通常不需要 |

### 目录结构

```
ops/git/
├── config.sh              # 配置文件 (⭐ 迁移时需要修改)
├── install_hooks.sh        # 安装脚本
├── commit/
│   ├── gen_commit_msg.py   # AI 生成 commit 消息
│   ├── commit_msg.sh       # commit-msg hook 逻辑
│   └── post-commit.sh      # post-commit hook 逻辑  
├── push/
│   ├── gen_pushlog.py      # AI 生成 push 日志
│   └── pre-push-hook.sh    # pre-push hook 逻辑
└── logs/
    ├── snapshots/          # commit 快照存储
    └── pushlogs/           # push 日志存储
```

## 工作流程

1. **Commit 阶段**：
   - `commit-msg` hook 调用 AI 生成 commit 消息
   - `post-commit` hook 保存 commit 快照到 `snapshots/`

2. **Push 阶段**：
   - `pre-push` hook 调用 AI 生成 push 总结
   - 自动将 `snapshots/` 中的快照归档到对应的 push 日志目录

## 依赖要求

- Python 3.7+
- 已配置的 GPT API 环境
- jq 命令行工具（用于 JSON 处理）

## 故障排查

### 常见问题

1. **Python 环境找不到**
   - 检查 `config.sh` 中的 `PYTHON_BIN` 路径
   - 确保虚拟环境已激活

2. **GPT 模块导入失败**
   - 检查 `GPT_MODULE_ROOT` 路径配置
   - 确保 GPT 相关模块在正确位置

3. **Prompt 文件读取失败**
   - 检查 `PROMPT_DIR` 路径配置
   - 确保所需的 prompt 文件存在

### 测试配置

```bash
# 测试配置是否正确
source ops/git/config.sh
echo "项目根路径: $PROJECT_ROOT"
echo "Python环境: $PYTHON_BIN"
echo "GPT模块: $GPT_MODULE_ROOT" 
echo "Prompt目录: $PROMPT_DIR"

# 测试 Python 环境
$PYTHON_BIN -c "import sys; print('Python OK:', sys.version)"

# 测试 GPT 模块导入
$PYTHON_BIN -c "
import sys
sys.path.append('$GPT_MODULE_ROOT')
from gpt.utils.direct_api import gptCaller
print('GPT 模块导入成功')
"
```
