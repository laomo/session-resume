#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


SAVE_SCRIPT = Path(__file__).parent / "save_session_id.py"


def load_json(path: Path):
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def hook_command(agent: str):
    return f'python3 "{SAVE_SCRIPT}" --agent {agent}'


def remove_session_hooks(groups: list, agent: str = None):
    cleaned = []
    for group in groups:
        hooks = []
        for hook in group.get("hooks", []):
            cmd = hook.get("command", "")
            if "session-resume/save_session_id.py" in cmd:
                # If agent is specified, only remove hooks matching that specific agent
                if agent and f"--agent {agent}" not in cmd:
                    hooks.append(hook)
            else:
                hooks.append(hook)
        if hooks:
            new_group = dict(group)
            new_group["hooks"] = hooks
            cleaned.append(new_group)
    return cleaned


def hook_exists(hooks: list, new_cmd: str) -> bool:
    """Check if a hook with the same command already exists."""
    for hook in hooks:
        if hook.get("command") == new_cmd:
            return True
    return False


def set_single_hook(data: dict, event: str, hook_group: dict, agent: str = None):
    hooks = data.setdefault("hooks", {})
    hook_list = hooks.get(event, [])
    new_cmd = hook_group["hooks"][0]["command"]

    # Skip if already installed
    if hook_exists(hook_list, new_cmd):
        return

    hooks[event] = remove_session_hooks(hook_list, agent)
    hooks[event].append(hook_group)


def install_codex():
    path = Path.home() / ".codex" / "hooks.json"
    data = load_json(path)
    set_single_hook(data, "Stop", {
        "hooks": [{
            "type": "command",
            "command": hook_command("codex"),
            "timeout": 10,
            "statusMessage": "Saving session ID",
        }]
    })
    save_json(path, data)
    return path


def install_claude():
    path = Path.home() / ".claude" / "settings.json"
    data = load_json(path)
    set_single_hook(data, "SessionEnd", {
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": hook_command("claude"),
            "timeout": 10,
        }]
    })
    save_json(path, data)
    return path


def install_gemini():
    path = Path.home() / ".gemini" / "settings.json"
    data = load_json(path)
    set_single_hook(data, "SessionEnd", {
        "matcher": "*",
        "hooks": [{
            "name": "save-session-id",
            "type": "command",
            "command": hook_command("gemini"),
            "timeout": 10,
        }]
    })
    save_json(path, data)
    return path


def main():
    parser = argparse.ArgumentParser(description="Install global session-resume hooks.")
    parser.add_argument("--agents", nargs="+", choices=["codex", "claude", "gemini"], default=["codex", "claude", "gemini"])
    args = parser.parse_args()

    installers = {
        "codex": install_codex,
        "claude": install_claude,
        "gemini": install_gemini,
    }
    for agent in args.agents:
        path = installers[agent]()
        print(f"installed {agent} hook in {path}")


if __name__ == "__main__":
    raise SystemExit(main())
