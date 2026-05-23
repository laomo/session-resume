#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_SESSION_FILE = ".agent-session.json"
CODEX_HISTORY_FILE = Path.home() / ".codex" / "history.jsonl"


def load_session_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Session file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Unsupported session file format: {path}")
    sessions = data.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError(f"Unsupported session file format: {path}")
    return data, sessions


def candidate_records(data: dict, sessions: list, agent: Optional[str]):
    candidates = [r for r in sessions if isinstance(r, dict)]
    if agent:
        candidates = [r for r in candidates if r.get("agent") == agent]
    return candidates


def unique_sessions(records: list):
    unique = []
    seen = set()
    for record in reversed([r for r in records if isinstance(r, dict)]):
        key = (record.get("agent"), record.get("session_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return list(reversed(unique))


def select_latest_record(data: dict, sessions: list, agent: Optional[str]):
    candidates = unique_sessions(candidate_records(data, sessions, agent))
    if not candidates:
        return None
    return candidates[-1]


def build_resume_command(record: dict, prompt: list[str]):
    agent = record.get("agent")
    session_id = record.get("session_id")
    if not session_id:
        raise ValueError("Selected record does not contain session_id")

    prompt_text = " ".join(prompt).strip()
    if agent == "codex":
        cmd = ["codex", "resume", session_id]
        if prompt_text:
            cmd.append(prompt_text)
        return cmd
    if agent == "claude":
        cmd = ["claude", "--resume", session_id]
        if prompt_text:
            cmd.append(prompt_text)
        return cmd
    if agent == "gemini":
        cmd = ["gemini", "--resume", session_id]
        if prompt_text:
            cmd.extend(["--prompt-interactive", prompt_text])
        return cmd

    raise ValueError(f"Unsupported agent for resume: {agent!r}")


def newest_first(records: list):
    return list(reversed([r for r in records if isinstance(r, dict)]))


def colorize(text: str, color_code: str):
    if not sys.stdout.isatty():
        return text
    return f"\033[{color_code}m{text}\033[0m"


def load_codex_history(path: Path = CODEX_HISTORY_FILE):
    by_session = {}
    if not path.exists():
        return by_session
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = item.get("session_id")
        text = item.get("text")
        if session_id and text and session_id not in by_session:
            by_session[session_id] = " ".join(str(text).split())
    return by_session


def truncate(value: str, width: int):
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "..."


def describe_record(record: dict):
    agent = record.get("agent", "unknown")
    session_id = record.get("session_id", "")
    saved_at = format_saved_at(record.get("saved_at", ""))
    return agent, saved_at, session_id


def format_saved_at(value: str):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def print_sessions(records: list):
    codex_history = load_codex_history()
    agent_width = max(11, *(len(str(record.get("agent", "unknown"))) for record in records))
    
    # Column widths
    w_id = 2
    w_agent = agent_width
    w_sid = 36
    w_saved = 19
    
    # Helper to print a row
    def print_row(id_str, agent_str, sid_str, saved_str, context_str, is_header=False):
        color = "1" if is_header else None
        
        # Format padded strings first
        f_id = f"{id_str:>{w_id}}"
        f_agent = f"{agent_str:<{w_agent}}"
        f_sid = f"{sid_str:<{w_sid}}"
        f_saved = f"{saved_str:<{w_saved}}"
        
        # Apply colors
        c_id = colorize(f_id, "1;36" if is_header else "36")
        c_agent = colorize(f_agent, "1;32" if is_header else "1;32")
        c_sid = colorize(f_sid, "1;90" if is_header else "90")
        c_saved = colorize(f_saved, "1;34" if is_header else "34")
        c_context = colorize(context_str, "1") if is_header else context_str
        
        print(f"{c_id}  {c_agent}  {c_sid}  {c_saved}  {c_context}")

    # Headers
    print_row("ID", "Agent", "Session ID", "Saved At", "Context", is_header=True)
    
    # Data rows
    for idx, record in enumerate(records, start=1):
        agent, saved_at, session_id = describe_record(record)
        context = session_context(record, codex_history)
        print_row(str(idx), agent, session_id, saved_at, context)


def session_context(record: dict, codex_history: dict):
    for key in ("title", "summary", "description", "prompt"):
        value = record.get(key)
        if value:
            return truncate(" ".join(str(value).split()), 80)
    if record.get("agent") == "codex":
        return truncate(codex_history.get(record.get("session_id"), ""), 80)
    return ""


def select_interactively(records: list):
    ordered = newest_first(records)
    if not ordered:
        return None

    print_sessions(ordered)
    while True:
        try:
            choice = input(f"Resume which session? [1-{len(ordered)}, q to quit]: ").strip()
        except EOFError:
            print("No selection received.", file=sys.stderr)
            return None
        if choice.lower() in {"q", "quit", "exit"}:
            return 0
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(ordered):
                return ordered[idx - 1]
        print("Invalid selection.", file=sys.stderr)


def print_selected(record: dict, cmd: list[str]):
    agent, saved_at, session_id = describe_record(record)
    print(f"Resuming {agent} session from {saved_at}: {session_id}", file=sys.stderr)
    print(f"Command: {shlex.join(cmd)}", file=sys.stderr)


def interactive_available():
    return sys.stdin.isatty() and sys.stdout.isatty()


def resolve_record(data: dict, sessions: list, agent: Optional[str], use_latest: bool):
    candidates = unique_sessions(candidate_records(data, sessions, agent))
    if not candidates:
        return None
    if use_latest or not interactive_available():
        return select_latest_record(data, sessions, agent)
    return select_interactively(candidates)


def print_sessions_for_list(records: list):
    print_sessions(newest_first(records))


def main():
    parser = argparse.ArgumentParser(description="Resume the latest recorded agent session for this directory.")
    parser.add_argument("--file", default=DEFAULT_SESSION_FILE,
                        help="Session JSON path. Defaults to .agent-session.json.")
    parser.add_argument("--agent", choices=["codex", "claude", "gemini"],
                        help="Resume the latest record for this agent.")
    parser.add_argument("--list", action="store_true", help="List recorded sessions, newest first.")
    parser.add_argument("--latest", action="store_true", help="Resume the latest matching record without prompting.")
    parser.add_argument("--print", action="store_true", help="Print the resume command instead of executing it.")
    parser.add_argument("prompt", nargs=argparse.REMAINDER, help="Optional prompt to pass to the resumed session.")
    args = parser.parse_args()

    path = Path(args.file).expanduser()
    data, sessions = load_session_file(path)
    candidates = unique_sessions(candidate_records(data, sessions, args.agent))

    if args.list:
        print_sessions_for_list(candidates)
        return 0

    record = resolve_record(data, sessions, args.agent, args.latest)
    if record == 0:
        return 0
    elif not record:
        qualifier = f" for agent {args.agent}" if args.agent else ""
        print(f"No recorded sessions found{qualifier} in {path}", file=sys.stderr)
        return 1

    cmd = build_resume_command(record, args.prompt)
    if args.print:
        print(shlex.join(cmd))
        return 0

    print_selected(record, cmd)
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    raise SystemExit(main())
