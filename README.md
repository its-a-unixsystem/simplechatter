# Simplechatter (LLM Debugger)

A lightweight, dependency-free Python CLI tool for debugging OpenAI-compatible chat completion APIs.

This tool allows you to interactively test chat completion endpoints, inspect request payloads, and experiment with different parameters without needing to install heavy dependencies.

## Requirements

- Python 3.x
- No external packages required (uses standard library `urllib`, `json`, `argparse`, etc.)

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

## Interactive Mode

Once started, you can type messages to send to the API.

### Slash Commands

- `/mode [user|assistant|system|json|raw]`
  - Switch input mode.
  - `user` (default): Input is sent as a user message.
  - `assistant`/`system`: Input is sent with the respective role.
  - `json`: Input must be a valid JSON message object or array of objects.
  - `raw`: Input is sent as the entire request body (no history logic).
- `/show` - Show the current conversation history.
- `/clear` - Clear the conversation history.
- `/quit` - Exit the debugger.
