#!/usr/bin/env python3
"""Multi-Agent Council CLI — interact with the council from the terminal.

Usage:
    multiagent-council review main.py
    multiagent-council chat "What is SOLID?"
    multiagent-council sessions
    multiagent-council setup

Environment:
    MULTIAGENT_COUNCIL_URL or QWEN_COUNCIL_URL  — API base URL (default: http://localhost:8000)
    QWEN_API_KEY      — Qwen Cloud API key (for setup command)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


DEFAULT_URL = os.environ.get("MULTIAGENT_COUNCIL_URL") or os.environ.get("QWEN_COUNCIL_URL") or "http://localhost:8000"
CONFIG_DIR = Path.home() / ".multiagent-council"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load CLI configuration from ~/.multiagent-council/config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    """Save CLI configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved to {CONFIG_FILE}")


def api_request(method: str, path: str, data: dict | None = None, timeout: int = 300) -> dict:
    """Make an API request to the Qwen Council server."""
    config = load_config()
    base_url = config.get("api_url", DEFAULT_URL).rstrip("/")
    url = urljoin(base_url + "/", path.lstrip("/"))

    headers = {"Content-Type": "application/json"}
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=timeout)
        else:
            resp = requests.post(url, headers=headers, json=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Qwen Council at {base_url}")
        print("Make sure the server is running or set MULTIAGENT_COUNCIL_URL")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: Request timed out. The council may be processing a large review.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}")
        if resp.text:
            print(f"Response: {resp.text[:500]}")
        sys.exit(1)


def cmd_review(args: argparse.Namespace) -> None:
    """Submit code for council review."""
    files = []
    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}")
            sys.exit(1)
        content = path.read_text()
        files.append({
            "filename": path.name,
            "content": content,
            "language": path.suffix.lstrip("."),
        })

    payload = {
        "files": files,
    }
    if args.instruction:
        payload["instruction"] = args.instruction

    print(f"Submitting {len(files)} file(s) for council review...")
    if args.instruction:
        print(f"Instruction: {args.instruction}")

    result = api_request("POST", "/api/review", data=payload)

    report = result.get("report", {})
    findings = report.get("findings", [])
    summary = report.get("summary", "")
    token_usage = report.get("token_usage", {})

    print(f"\n{'='*60}")
    print(f"  COUNCIL REPORT — {result.get('session_id', 'unknown')}")
    print(f"{'='*60}")
    print(f"\nFindings: {len(findings)}")

    # Token usage
    if token_usage:
        total = token_usage.get("total_tokens", 0)
        cost = token_usage.get("estimated_cost_usd", 0)
        model = token_usage.get("model", "unknown")
        print(f"Model: {model}")
        print(f"Tokens: {total:,} (input: {token_usage.get('total_input_tokens', 0):,}, output: {token_usage.get('total_output_tokens', 0):,})")
        print(f"Est. cost: ${cost:.4f}")

    # Summary
    if summary:
        print(f"\n{'─'*60}")
        print("EXECUTIVE SUMMARY")
        print(f"{'─'*60}")
        print(textwrap.fill(summary, width=80))

    # Findings by severity
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        sev = f.get("impact", "Low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    print(f"\n{'─'*60}")
    print("SEVERITY")
    print(f"{'─'*60}")
    for sev, count in severity_counts.items():
        bar = "█" * count
        print(f"  {sev:10s} {count:3d} {bar}")

    # Top findings
    if findings:
        print(f"\n{'─'*60}")
        print("TOP FINDINGS")
        print(f"{'─'*60}")
        for i, f in enumerate(findings[:5], 1):
            print(f"\n  {i}. [{f.get('impact', '?')}] {f.get('title', '')}")
            if f.get("proposal"):
                print(f"     → {f.get('proposal')[:120]}")


def cmd_chat(args: argparse.Namespace) -> None:
    """Ask the expert panel a question."""
    question = " ".join(args.question)
    print(f"Asking: {question}")

    payload = {"message": question}
    if args.session:
        payload["session_id"] = args.session

    result = api_request("POST", "/api/chat", data=payload)

    print(f"\n{'='*60}")
    print(f"  EXPERT PANEL — {result.get('session_id', 'unknown')}")
    print(f"{'='*60}")
    print(f"\n{result.get('response', '')}")

    contributions = result.get("agent_contributions", [])
    if contributions:
        print(f"\n{'─'*60}")
        print(f"AGENT CONTRIBUTIONS ({len(contributions)} agents)")
        print(f"{'─'*60}")
        for c in contributions:
            agent = c.get("agent", "")
            answer = c.get("answer", "")
            print(f"\n  [{agent}]")
            print(f"  {answer}")


def cmd_sessions(args: argparse.Namespace) -> None:
    """List past review sessions."""
    sessions = api_request("GET", "/api/sessions")

    if not sessions:
        print("No sessions found.")
        return

    print(f"\n{'='*60}")
    print(f"  SESSIONS ({len(sessions)} total)")
    print(f"{'='*60}")
    print(f"\n{'ID':<20s} {'Preview':<30s} {'Score':>6s} {'Findings':>10s}")
    print(f"{'─'*20} {'─'*30} {'─'*6} {'─'*10}")

    for s in sessions:
        sid = s.get("id", "")[:18]
        preview = s.get("code_preview", "")[:28]
        score = s.get("score", 0)
        findings = s.get("finding_count", 0)
        print(f"{sid:<20s} {preview:<30s} {score:>6.2f} {findings:>10d}")


def cmd_setup(args: argparse.Namespace) -> None:
    """Configure the CLI with API URL and key."""
    config = load_config()

    if args.url:
        config["api_url"] = args.url
    elif "api_url" not in config:
        url = input(f"API URL [{DEFAULT_URL}]: ").strip()
        config["api_url"] = url or DEFAULT_URL

    if args.api_key:
        config["api_key"] = args.api_key
    elif "api_key" not in config:
        key = input("Qwen Cloud API key: ").strip()
        if key:
            config["api_key"] = key

    save_config(config)

    # Verify connection
    print("\nVerifying connection...")
    try:
        health = api_request("GET", "/api/health")
        print(f"✓ Connected: {health.get('status', 'unknown')}")
    except SystemExit:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="multiagent-council",
        description="Multi-Agent Council CLI — multi-agent code review and chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              multiagent-council review main.py
              multiagent-council review main.py utils.py --instruction "Focus on security"
              multiagent-council chat "What is the meaning of life?"
              multiagent-council sessions
              multiagent-council setup
        """),
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # review
    review_parser = subparsers.add_parser("review", help="Submit code for council review")
    review_parser.add_argument("files", nargs="+", help="Source files to review")
    review_parser.add_argument("--instruction", "-i", help="Review instruction")
    review_parser.set_defaults(func=cmd_review)

    # chat
    chat_parser = subparsers.add_parser("chat", help="Ask the expert panel a question")
    chat_parser.add_argument("question", nargs="+", help="Question to ask")
    chat_parser.add_argument("--session", "-s", help="Session ID for context")
    chat_parser.set_defaults(func=cmd_chat)

    # sessions
    sessions_parser = subparsers.add_parser("sessions", help="List past sessions")
    sessions_parser.set_defaults(func=cmd_sessions)

    # setup
    setup_parser = subparsers.add_parser("setup", help="Configure API URL and key")
    setup_parser.add_argument("--url", help="API base URL")
    setup_parser.add_argument("--api-key", help="Qwen Cloud API key")
    setup_parser.set_defaults(func=cmd_setup)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
