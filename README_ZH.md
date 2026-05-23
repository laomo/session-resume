# Session Resume

自动将 Agent 会话 ID 保存到**当前项目目录**，一条命令即可快捷恢复之前的对话。支持 Codex、Claude Code 和 Gemini CLI。

## 安装

```bash
# 克隆仓库
mkdir -p ~/.agents
git clone https://github.com/laomo/session-resume ~/.agents/session-resume

# 安装 CLI 快捷命令
mkdir -p ~/.local/bin
ln -sf ~/.agents/session-resume/resume_session.py ~/.local/bin/resume_session

# 注册会话结束时的 hook
./install_hooks.py

# 重载 shell
source ~/.zshrc
```

安装程序会在以下位置注册 hook：

- Codex: `~/.codex/hooks.json`
- Claude Code: `~/.claude/settings.json`
- Gemini CLI: `~/.gemini/settings.json`

## 工作原理

每次 Agent 会话结束时，hook 自动将会话 ID 保存到工作目录的 `.agent-session.json` 文件中。会话存储在一个只增不减的 `sessions` 数组中，并从第一条 prompt 提取 `title` 字段，方便识别和恢复。

### 会话 ID 来源

| Agent       | 环境变量                                      |
|-------------|---------------------------------------------|
| Codex       | `CODEX_THREAD_ID`, `CODEX_SESSION_ID`         |
| Claude Code | `CLAUDE_SESSION_ID`, `CLAUDE_CONVERSATION_ID` |
| Gemini      | `GEMINI_SESSION_ID`, `GEMINI_CONVERSATION_ID` |


## 恢复会话

列出当前目录记录的会话：

```bash
resume_session --list
```

交互式选择并恢复会话：

```bash
resume_session
```

直接恢复最新会话（无需选择）：

```bash
resume_session --latest
```

预览恢复命令但不启动：

```bash
resume_session --latest --print
```

恢复操作支持 Codex（`codex resume`）、Claude Code（`claude --resume`）和 Gemini CLI（`gemini --resume`）。

## 手动验证

手动保存会话：

```bash
python3 ~/.agents/session-resume/save_session_id.py --session-id "$SESSION_ID" --agent claude
```