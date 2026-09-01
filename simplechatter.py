#!/usr/bin/env python3
import argparse
import json
import os
import urllib.error
import urllib.request

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Very simple OpenAI-compatible chat completions debugger."
    )
    parser.add_argument("--url", required=True, help="Full chat/completions endpoint URL.")
    parser.add_argument("--model", required=True, help="Model name to send in payload.")
    parser.add_argument("--api-token", help="API token. Falls back to env var in --api-token-env.")
    parser.add_argument(
        "--api-token-env",
        default="OPENAI_API_KEY",
        help="Env var name used when --api-token is not provided.",
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, help="Optional provider-specific top_k.")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        help="Optional provider-specific reasoning effort.",
    )
    parser.add_argument(
        "--extra-params",
        help="Optional JSON object merged into request payload for provider-specific params.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--initial-input",
        help="Initial message to send before entering interactive mode.",
    )
    parser.add_argument(
        "--interface",
        choices=["plain", "rich"],
        default="plain",
        help="Interface style for prompts and output.",
    )
    parser.add_argument(
        "--user-agent",
        default="simplechatter/1.0",
        help="User-Agent header sent with requests.",
    )
    return parser


def post_json(url: str, token: str, payload: dict, timeout: float, user_agent: str | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if user_agent:
        headers["User-Agent"] = user_agent
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def parse_extra_params(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"--extra-params is not valid JSON: {e}") from e
    if not isinstance(parsed, dict):
        raise ValueError("--extra-params must be a JSON object.")
    return parsed


def parse_json_message(text: str) -> list[dict]:
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        if "role" not in parsed or "content" not in parsed:
            raise ValueError("JSON object must contain role and content.")
        return [parsed]
    if isinstance(parsed, list):
        out = []
        for item in parsed:
            if not isinstance(item, dict) or "role" not in item or "content" not in item:
                raise ValueError("Each JSON list item must be an object with role and content.")
            out.append(item)
        return out
    raise ValueError("JSON message must be an object or a list of objects.")


def extract_assistant_text(raw_body: str) -> str | None:
    try:
        parsed = json.loads(raw_body)
        return parsed["choices"][0]["message"]["content"]
    except Exception:
        return None


def build_payload(
    model: str,
    messages: list[dict],
    temperature: float,
    top_p: float,
    top_k: int | None,
    max_tokens: int,
    reasoning_effort: str | None,
    extra_params: dict,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if top_k is not None:
        payload["top_k"] = top_k
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    payload.update(extra_params)
    return payload


def format_json(raw: str) -> str | None:
    try:
        return json.dumps(json.loads(raw), indent=2, ensure_ascii=True)
    except json.JSONDecodeError:
        return None


def print_help(interface: str, console: Console) -> None:
    if interface == "rich":
        commands = Table(show_header=True, header_style="bold")
        commands.add_column("Command")
        commands.add_column("Description")
        commands.add_row("/mode user|assistant|system|json|raw|none", "Switch input mode")
        commands.add_row("/interface plain|rich", "Switch interface style")
        commands.add_row("/show", "Show current history")
        commands.add_row("/clear", "Clear history")
        commands.add_row("/quit", "Exit")

        modes = Table(show_header=True, header_style="bold")
        modes.add_column("Mode")
        modes.add_column("Behavior")
        modes.add_row("user/assistant/system", "Input becomes one message and is appended to history")
        modes.add_row("json", "Input must be a JSON message object or array, appended to history")
        modes.add_row("raw", "Input is sent as the entire request body, no history modification")

        console.print(Panel(commands, title="Commands", border_style="cyan"))
        console.print(Panel(modes, title="Modes", border_style="cyan"))
        return

    console.print("Commands:")
    console.print("  /mode user|assistant|system|json|raw|none   Switch input mode")
    console.print("  /interface plain|rich                  Switch interface style")
    console.print("  /show                                  Show current history")
    console.print("  /clear                                 Clear history")
    console.print("  /quit                                  Exit")
    console.print("")
    console.print("Modes:")
    console.print("  user/assistant/system -> input becomes one message and is appended to history")
    console.print("  json -> input must be JSON message object or array, appended to history")
    console.print("  raw -> input sent as entire request body, no history modification")


def print_status(status: int, interface: str, console: Console) -> None:
    if interface == "rich":
        style = "green" if 200 <= status < 300 else "red"
        console.print(Text(f"HTTP {status}", style=f"bold {style}"))
        return
    console.print(f"HTTP {status}")


def print_body(raw_body: str, interface: str, console: Console) -> None:
    if interface == "rich":
        formatted = format_json(raw_body)
        if formatted is None:
            console.print(raw_body)
        else:
            console.print(JSON(formatted))
        return
    console.print(raw_body)


def print_history(history: list[dict], interface: str, console: Console) -> None:
    formatted = json.dumps(history, indent=2, ensure_ascii=True)
    if interface == "rich":
        console.print(Panel(JSON(formatted), title="History", border_style="cyan"))
        return
    console.print(formatted)


def read_input(prompt: str, interface: str, console: Console) -> str:
    if interface == "rich":
        return console.input(Text(prompt, style="bold cyan"))
    return console.input(prompt)


def print_line(text: str, interface: str, console: Console, style: str | None = None) -> None:
    if interface == "rich":
        console.print(text, style=style)
        return
    console.print(text)


def print_error(text: str, interface: str, console: Console) -> None:
    if interface == "rich":
        console.print(text, style="red")
        return
    console.print(text)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    console = Console()
    error_console = Console(stderr=True)

    token = args.api_token or os.getenv(args.api_token_env)
    if not token:
        print_error(
            f"Error: API token missing. Use --api-token or ${args.api_token_env}.",
            args.interface,
            error_console,
        )
        return 2

    try:
        extra_params = parse_extra_params(args.extra_params)
    except ValueError as e:
        print_error(f"Error: {e}", args.interface, error_console)
        return 2

    mode = "user"
    interface = args.interface
    history: list[dict] = []

    print_line("Simple chat debugger started.", interface, console, style="bold")
    print_line(f"Endpoint: {args.url}", interface, console)
    print_line(f"Model: {args.model}", interface, console)
    print_help(interface, console)

    pending_input: str | None = args.initial_input

    while True:
        if pending_input is not None:
            text = pending_input.strip()
            pending_input = None
            print_line(f"[{mode}]> {text}", interface, console, style="cyan")
        else:
            try:
                text = read_input(f"[{mode}]> ", interface, console).strip()
            except EOFError:
                print_line("", interface, console)
                break
            except KeyboardInterrupt:
                print_line("\nInterrupted.", interface, console)
                break

        if not text:
            continue

        if text == "/quit":
            break
        if text == "/show":
            print_history(history, interface, console)
            continue
        if text == "/clear":
            history.clear()
            print_line("History cleared.", interface, console, style="green")
            continue
        if text.startswith("/interface "):
            candidate = text.split(maxsplit=1)[1].strip().lower()
            if candidate in {"plain", "rich"}:
                interface = candidate
                print_line(f"Interface set to: {interface}", interface, console, style="green")
            else:
                print_line("Invalid interface.", interface, console, style="red")
            continue
        if text.startswith("/mode "):
            candidate = text.split(maxsplit=1)[1].strip().lower()
            if candidate == "none":
                candidate = "raw"
            if candidate in {"user", "assistant", "system", "json", "raw"}:
                mode = candidate
                print_line(f"Mode set to: {mode}", interface, console, style="green")
            else:
                print_line("Invalid mode.", interface, console, style="red")
            continue

        if mode == "raw":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as e:
                print_line(f"Invalid raw JSON body: {e}", interface, console, style="red")
                continue
        else:
            new_messages: list[dict]
            if mode == "json":
                try:
                    new_messages = parse_json_message(text)
                except (ValueError, json.JSONDecodeError) as e:
                    print_line(f"Invalid JSON message input: {e}", interface, console, style="red")
                    continue
            else:
                new_messages = [{"role": mode, "content": text}]

            history.extend(new_messages)
            payload = build_payload(
                model=args.model,
                messages=history,
                temperature=args.temperature,
                top_p=args.top_p,
                top_k=args.top_k,
                max_tokens=args.max_tokens,
                reasoning_effort=args.reasoning_effort,
                extra_params=extra_params,
            )

        status, raw_body = post_json(args.url, token, payload, timeout=args.timeout, user_agent=args.user_agent)
        print_status(status, interface, console)
        print_body(raw_body, interface, console)

        if mode != "raw" and 200 <= status < 300:
            assistant_text = extract_assistant_text(raw_body)
            if assistant_text is not None:
                history.append({"role": "assistant", "content": assistant_text})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
