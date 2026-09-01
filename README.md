# Simplechatter (LLM Debugger)

A lightweight Python CLI tool for debugging OpenAI-compatible chat completion APIs.

This tool allows you to interactively test chat completion endpoints, inspect request payloads, and experiment with different parameters.

## Requirements

- Python 3.x
- Rich for terminal formatting

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

Run the script directly with Python. You must provide the endpoint URL and the model name.

```bash
# Basic usage with an API key env var (defaults to OPENAI_API_KEY)
export OPENAI_API_KEY="sk-..."
python3 simplechatter.py --url "https://api.openai.com/v1/chat/completions" --model "gpt-3.5-turbo"

# Usage with a specific API key passed as an argument
python3 simplechatter.py \
  --url "https://api.openai.com/v1/chat/completions" \
  --model "gpt-4" \
  --api-token "sk-..."

# Send an initial message automatically on startup
python3 simplechatter.py \
  --url "https://api.openai.com/v1/chat/completions" \
  --model "gpt-4" \
  --initial-input "Hello, how are you?"

# Start with formatted terminal output
python3 simplechatter.py \
  --url "https://api.openai.com/v1/chat/completions" \
  --model "gpt-4" \
  --interface rich
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--url` | **Required**. Full chat/completions endpoint URL. | - |
| `--model` | **Required**. Model name to send in payload. | - |
| `--api-token` | API token. | - |
| `--api-token-env` | Environment variable name for the API token. | `OPENAI_API_KEY` |
| `--temperature` | Sampling temperature. | `0.7` |
| `--top-p` | Nucleus sampling probability. | `1.0` |
| `--top-k` | Provider-specific top-k. | - |
| `--max-tokens` | Maximum tokens to generate. | `512` |
| `--reasoning-effort` | Provider-specific reasoning effort (low/medium/high). | - |
| `--extra-params` | JSON object for provider-specific parameters. | - |
| `--timeout` | Request timeout in seconds. | `60.0` |
| `--initial-input` | Initial message to send before entering interactive mode. | - |
| `--interface` | Interface style (`plain` or `rich`). | `plain` |
| `--user-agent` | Optional User-Agent header for client fingerprint gating. | - |

### Client Fingerprinting

Some API providers (like agentrouter.org, coding-plan relays) gate requests based on the User-Agent header, only allowing recognized coding-agent clients. For these providers, pass `--user-agent` with an approved client string:

```bash
python3 simplechatter.py \
  --url "https://agentrouter.org/v1/chat/completions" \
  --model "glm-5.3" \
  --api-token "sk-..." \
  --user-agent "claude-cli/2.1.220 (external, cli)"
```

Without `--user-agent`, simplechatter sends Python's default User-Agent (or none), which works with standard OpenAI-compatible providers but may be rejected by fingerprinting gateways with `401 unauthorized client detected`.

## Interactive Mode

Once started, you can type messages to send to the API.
Successful assistant replies are added back to the conversation history, so follow-up messages keep context.

### Slash Commands

- `/mode [user|assistant|system|json|raw]`
  - Switch input mode.
  - `user` (default): Input is sent as a user message.
  - `assistant`/`system`: Input is sent with the respective role.
  - `json`: Input must be a valid JSON message object or array of objects.
  - `raw`: Input is sent as the entire request body (no history logic).
  - `none`: Alias for `raw`.
- `/interface [plain|rich]`
  - Switch interface style.
  - `plain`: Prints simple text output.
  - `rich`: Uses formatted prompts, tables, status output, history panels, and pretty JSON response bodies.
- `/show` - Show the current conversation history.
- `/clear` - Clear the conversation history.
- `/quit` - Exit the debugger.

### JSON Modes

Use `json` mode when you want to append one or more structured messages to the normal chat history:

```text
/mode json
{"role": "system", "content": "Answer tersely."}
```

Use `raw` mode when you want to send the entire request body yourself:

```text
/mode raw
{"model": "gpt-4", "messages": [{"role": "user", "content": "Ping"}]}
```

Raw mode bypasses automatic history updates and parameter merging.
