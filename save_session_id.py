#!/usr/bin/env python3
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CODEX_HISTORY_FILE = Path.home() / ".codex" / "history.jsonl"
CLAUDE_HISTORY_FILE = Path.home() / ".claude" / "history.jsonl"

SESSION_ENV_VARS = [
    ("codex", "CODEX_THREAD_ID"),
    ("codex", "CODEX_SESSION_ID"),
    ("claude", "CLAUDE_SESSION_ID"),
    ("claude", "CLAUDE_CONVERSATION_ID"),
    ("gemini", "GEMINI_SESSION_ID"),
    ("gemini", "GEMINI_CONVERSATION_ID"),
    ("agent", "AGENT_SESSION_ID"),
    ("agent", "SESSION_ID"),
]


def read_hook_input():
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        print("Ignoring non-JSON hook stdin.", file=sys.stderr)
        return {}
    return value if isinstance(value, dict) else {}


def detect_session(agent_hint: Optional[str] = None):
    if agent_hint:
        for agent, env_name in SESSION_ENV_VARS:
            if agent != agent_hint:
                continue
            value = os.environ.get(env_name)
            if value:
                return agent, env_name, value

    for agent, env_name in SESSION_ENV_VARS:
        value = os.environ.get(env_name)
        if value:
            return agent, env_name, value

    return None, None, None


def detect_cwd(payload: dict):
    cwd = payload.get("cwd")
    if cwd:
        return Path(cwd)
    for env_name in ("CLAUDE_PROJECT_DIR", "GEMINI_PROJECT_DIR", "PWD"):
        value = os.environ.get(env_name)
        if value:
            return Path(value)
    return Path.cwd()


def normalize_text(value):
    return " ".join(str(value).split())


def first_codex_prompt(session_id: str, path: Path = CODEX_HISTORY_FILE):
    if not session_id or not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("session_id") == session_id and item.get("text"):
            return normalize_text(item["text"])
    return None


def first_claude_prompt(session_id: str, path: Path = CLAUDE_HISTORY_FILE):
    if not session_id or not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("sessionId") == session_id and item.get("display"):
            return normalize_text(item["display"])
    return None


def first_gemini_prompt(transcript_path_str: str):
    if not transcript_path_str:
        return None
    path = Path(transcript_path_str)
    if not path.exists():
        return None
    try:
        # Gemini 的 transcript 文件是 JSONL 格式（每行一个 JSON 对象）
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                turn = json.loads(line)
                if isinstance(turn, dict) and turn.get("type") == "user" and turn.get("content"):
                    return normalize_gemini_text(turn["content"])
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return None


def normalize_gemini_text(value):
    return " ".join([item["text"] for item in value])


def detect_title(agent: str, session_id: str, transcript_path: str = None):
    if agent == "codex":
        return first_codex_prompt(session_id)
    elif agent == "claude":
        return first_claude_prompt(session_id)
    elif agent == "gemini":
        if transcript_path:
            title = first_gemini_prompt(transcript_path)
            if title:
                return title
    return None


def atomic_write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def ensure_ignored(path: Path):
    gitignore = path.parent / ".gitignore"
    filename = path.name
    try:
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if filename in content.splitlines():
                return
            # Ensure newline before appending if needed
            suffix = "\n" if content and not content.endswith("\n") else ""
            with gitignore.open("a", encoding="utf-8") as f:
                f.write(f"{suffix}{filename}\n")
        else:
            gitignore.write_text(f"{filename}\n", encoding="utf-8")
    except Exception:
        pass


def load_existing(path: Path):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        ensure_ignored(path)
        return {"sessions": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("sessions"), list):
        return data
    raise ValueError(f"Unsupported session file format: {path}")


def append_session(path: Path, record: dict):
    data = load_existing(path)
    sessions = data.setdefault("sessions", [])
    sessions.append(record)
    data["sessions"] = dedupe_sessions(sessions)
    # data["sessions"] = sessions
    atomic_write_json(path, data)


def dedupe_sessions(sessions: list):
    deduped = []
    seen = set()
    for session in reversed([s for s in sessions if isinstance(s, dict)]):
        key = (session.get("agent"), session.get("session_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(session)
    return list(reversed(deduped))


def main():
    parser = argparse.ArgumentParser(description="Append the current agent session ID into this directory.")
    parser.add_argument("--session-id", help="Session ID to save. Defaults to hook stdin or known agent env vars.")
    parser.add_argument("--agent", help="Agent name to save. Defaults to the detected agent.")
    parser.add_argument("--output", default=".agent-session.json",
                        help="Output JSON path. Defaults to .agent-session.json.")
    args = parser.parse_args()

    payload = read_hook_input()
    detected_agent, source_env, detected_session_id = detect_session(args.agent)
    payload_session_id = payload.get("session_id")
    agent = args.agent or detected_agent or "unknown"
    session_id = args.session_id or detected_session_id or payload_session_id

    if not session_id:
        env_names = ", ".join(env_name for _, env_name in SESSION_ENV_VARS)
        print(f"No session ID found. Set one of: {env_names}, or pass --session-id.", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser()
    cwd = detect_cwd(payload)
    if not output.is_absolute():
        output = cwd / output

    record = {
        "agent": agent,
        # "payload": payload,
        "hook_event_name": payload.get("hook_event_name"),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "source": "argument" if args.session_id else (source_env if detected_session_id else "stdin"),
        "source_env": source_env if not args.session_id and detected_session_id else None,
    }
    title = detect_title(agent, session_id, payload.get("transcript_path"))
    if title:
        record["title"] = title
    append_session(output, record)
    print(f"Appended {agent} session ID to {output}", file=sys.stderr)
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
