# AGENTS.md

## Overview

Simplechatter is a lightweight Python CLI tool for debugging OpenAI-compatible
chat completion APIs. Single-file app (`simplechatter.py`, stdlib + Rich only),
no framework, no build step.

The repo also contains two supporting areas:

- `test_simplechatter.py` — a **testing app** (unittest-based). It drives the
  real CLI `main()` with mocked `post_json`/stdin and asserts on actual terminal
  output. Run with `python3 test_simplechatter.py` or
  `python3 -m unittest test_simplechatter.py`. Use it as the pattern for new
  tests: patch `simplechatter.post_json` and `builtins.input`, redirect stdout,
  assert on observable CLI behavior — never on internals.
- `pricing-comparison/` — a token-pricing dataset comparing 7 providers
  (openrouter, unorouter, raunai, oneprovider, nano-gpt, anymodel, b.ai). See
  `pricing-comparison/README.md` for schema, refresh procedure, and query
  usage. The dataset (`models.jsonl`) is machine-generated; regenerate with
  `python3 normalize.py`, never hand-edit.

## Commands

```bash
python3 -m pip install -r requirements.txt   # just 'rich'
python3 test_simplechatter.py                # run the test suite
python3 simplechatter.py --url <endpoint> --model <model>   # run the app
```

No linter/formatter config exists; match the existing style of the file you are
editing.

## Conventions

- Everything user-facing lives in `simplechatter.py`; keep it single-file.
- Slash-commands in the interactive loop (e.g. `/interface rich`) are the
  extension point for new runtime features; args are parsed via `argparse`.
- Tests use only stdlib `unittest` + `unittest.mock` — do not add test
  dependencies.
- Git commits follow Conventional Commits (`feat(cli): ...`,
  `fix: ...`).

## Working agreements

- Do not hand-edit generated data (`models.jsonl`, `*_raw.json[l]`); rerun the
  generator scripts instead.
- The pricing scrapers hit live third-party sites; keep the per-request sleep
  in `scrape_unorouter.py` and don't parallelize it.
- Report network/parse failures per provider rather than aborting the whole
  normalization run.
