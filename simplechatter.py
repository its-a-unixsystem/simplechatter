#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


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
    return parser


def post_json(url: str, token: str, payload: dict, timeout: float) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
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


def print_help() -> None:
    print("Commands:")
    print("  /mode user|assistant|system|json|raw|none   Switch input mode")
    print("  /show                                  Show current history")
    print("  /clear                                 Clear history")
    print("  /quit                                  Exit")
    print("")
    print("Modes:")
    print("  user/assistant/system -> input becomes one message and is appended to history")
    print("  json -> input must be JSON message object or array, appended to history")
    print("  raw -> input sent as entire request body, no history modification")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    token = args.api_token or os.getenv(args.api_token_env)
    if not token:
        print(
            f"Error: API token missing. Use --api-token or ${args.api_token_env}.",
            file=sys.stderr,
        )
        return 2

    try:
        extra_params = parse_extra_params(args.extra_params)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    mode = "user"
    history: list[dict] = []

    print("Simple chat debugger started.")
    print(f"Endpoint: {args.url}")
    print(f"Model: {args.model}")
    print_help()

    pending_input: str | None = args.initial_input

    while True:
        if pending_input is not None:
            text = pending_input.strip()
            pending_input = None
            print(f"[{mode}]> {text}")
        else:
            try:
                text = input(f"[{mode}]> ").strip()
            except EOFError:
                print("")
                break
            except KeyboardInterrupt:
                print("\nInterrupted.")
                break

        if not text:
            continue

        if text == "/quit":
            break
        if text == "/show":
            print(json.dumps(history, indent=2, ensure_ascii=True))
            continue
        if text == "/clear":
            history.clear()
            print("History cleared.")
            continue
        if text.startswith("/mode "):
            candidate = text.split(maxsplit=1)[1].strip().lower()
            if candidate == "none":
                candidate = "raw"
            if candidate in {"user", "assistant", "system", "json", "raw"}:
                mode = candidate
                print(f"Mode set to: {mode}")
            else:
                print("Invalid mode.")
            continue

        if mode == "raw":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as e:
                print(f"Invalid raw JSON body: {e}")
                continue
        else:
            new_messages: list[dict]
            if mode == "json":
                try:
                    new_messages = parse_json_message(text)
                except (ValueError, json.JSONDecodeError) as e:
                    print(f"Invalid JSON message input: {e}")
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

        status, raw_body = post_json(args.url, token, payload, timeout=args.timeout)
        print(f"HTTP {status}")
        print(raw_body)

        if mode != "raw" and 200 <= status < 300:
            assistant_text = extract_assistant_text(raw_body)
            if assistant_text is not None:
                history.append({"role": "assistant", "content": assistant_text})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
