# Session Resume

Automatically save agent session IDs into the **current project directory** and resume past conversations with a single quick command. Supports Codex, Claude Code, and Gemini CLI.

## Install

```bash
# Clone repository
mkdir -p ~/.agents
git clone https://github.com/laomo/session-resume ~/.agents/session-resume

# Install CLI shortcut
mkdir -p ~/.local/bin
ln -sf ~/.agents/session-resume/resume_session.py ~/.local/bin/resume_session

# Register session-end hooks
./install_hooks.py

# Reload shell
source ~/.zshrc
```

The installer registers hooks in:

- Codex: `~/.codex/hooks.json`
- Claude Code: `~/.claude/settings.json`
- Gemini CLI: `~/.gemini/settings.json`

## How it works

Each time an agent session ends, the hook automatically saves the session ID to `.agent-session.json` in the working directory. Sessions are stored in an append-only `sessions` array with a `title` derived from the first prompt, making it easy to identify and resume later.

### Session ID sources

| Agent       | Environment variables                         |
|-------------|----------------------------------------------|
| Codex       | `CODEX_THREAD_ID`, `CODEX_SESSION_ID`         |
| Claude Code | `CLAUDE_SESSION_ID`, `CLAUDE_CONVERSATION_ID` |
| Gemini      | `GEMINI_SESSION_ID`, `GEMINI_CONVERSATION_ID` |


## Resume sessions

List recorded sessions for the current directory:

```bash
resume_session --list
```

Resume the latest session interactively:

```bash
resume_session
```

Resume the latest session directly (no prompt):

```bash
resume_session --latest
```

Preview the resume command without launching:

```bash
resume_session --latest --print
```

Resume is supported for Codex (`codex resume`), Claude Code (`claude --resume`), and Gemini CLI (`gemini --resume`).

## Manual verification

Save a session manually:

```bash
python3 ~/.agents/session-resume/save_session_id.py --session-id "$SESSION_ID" --agent claude
```