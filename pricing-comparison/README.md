# Token pricing comparison dataset

Normalized per-token (and per-image) pricing across 7 providers/proxies, for
asking things like "show me prices for Opus 5".

## Files

| file | what |
|---|---|
| `models.jsonl` | **the dataset** — one record per (model x free/paid variant x provider) |
| `query.py` | CLI to query it |
| `normalize.py` | raw data -> `models.jsonl` (also exposes `canonicalize()`) |
| `*_raw.json[l]` / `*.html` / `*.js` | raw provider data as fetched — gitignored (regenerable); kept for diffing between refreshes. `bai_raw.json` is tracked since its source lives outside the repo |
| `scrape_unorouter.py` | UnoRouter scraper (embedded Next.js flight-data extraction) |

## Record schema

```jsonc
{
  "canonical": "claude-opus-4-8",   // sanitized id; joins providers together
  "display_name": "Claude Opus 4.8",
  "vendor": "anthropic",            // upstream model vendor, not the proxy
  "output_type": "text",            // text | image | video | audio | embedding
  "free": false,                    // true = zero-cost variant of a model that may also have a paid variant
  "context": 1000000,               // context tokens, null if unknown
  "source": {
    "provider": "openrouter",       // openrouter | unorouter | raunai | oneprovider | nano-gpt | anymodel | b.ai
    "model_id": "anthropic/claude-opus-4.8",
    "url": "https://openrouter.ai/models",   // remember where it came from — refresh source
    "retrieved": "2026-09-01"
  },
  "usd_per_1m": {                   // all keys optional, all USD per 1M tokens unless noted
    "input": 5.0,
    "output": 25.0,
    "cache_read": 0.5,
    "cache_write": 6.25,            // 5m write
    "cache_write_1h": 10.0,
    "image": 120.0,                 // image OUTPUT tokens (per 1M) — or per-image price where provider bills that way
    "input_audio": 2.0, "output_audio": 2.0,
    "flat_input_output": 0.3,       // anymodel-style single flat rate
    "input_above_200k": 10.0        // nano-gpt long-context tier
  },
  "notes": "..."                    // pricing caveats (discounts, multipliers, subscription)
}
```

All prices normalized to **USD per 1M tokens** (openrouter gives per-token —
multiplied by 1e6; nano-gpt gives per-1k — multiplied by 1e3).

## Querying

```sh
python3 query.py "claude opus 5"          # paid prices per provider
python3 query.py "claude opus 5" --all    # include free variants
python3 query.py "glm 5.3" --free         # free variants only
python3 query.py "gpt-5.6" --all --json   # machine-readable
```

Names are canonicalized before matching, so `claude-opus-4.8`, `claude opus 4.8`,
`Claude Opus 4.8`, `anthropic/claude-opus-4.8` all hit the same record. No exact
match falls back to substring family listing with cheapest prices.

Or just grep:

```sh
grep '"canonical": "claude-opus-5"' models.jsonl | grep -v '"free": true' | jq -s 'sort_by(.usd_per_1m.input)'
```

## Refreshing

Each source URL is stored in every record (`source.url`). Re-fetch:

- **openrouter**: `curl https://openrouter.ai/api/v1/models` (public API)
- **nano-gpt**: `curl https://nano-gpt.com/api/models` (public API; has both
  cost strings and numeric per-million fields)
- **unorouter**: `python3 scrape_unorouter.py` (walks per-vendor pages, decodes
  embedded Next.js flight data — no public JSON API found). The script then
  cross-checks against `unorouter.com/sitemap.xml` and fetches any missing
  model pages directly (offline models are excluded from vendor-page flight
  data but still listed in the sitemap); it reports `ok`/`NOT FOUND` per
  fallback so gaps are visible.
- **raunai**: parse `https://raunai.com/pricing` HTML (static, crawlable)
- **oneprovider**: parse `https://oneprovider.dev/assets/model-catalog-*.js`
  (SPA; catalog chunk has `pricing_per_mtok` list prices — effective price =
  list x0.125, the 8x top-up credit multiplier)
- **anymodel**: parse `https://anymodel.org/en/pricing` HTML table (API requires a key)
- **b.ai**: no public page; copied from `~/model_pricing_data.jsonl`

Then run `python3 normalize.py` to rebuild `models.jsonl`.

## Caveats baked into the data

- **free vs paid**: same model can appear twice — `"free": true` (e.g.
  `glm-5.3:free` on unorouter) and paid. Filter with the `free` field.
- **b.ai**: subscription ($30/mo) rather than pay-per-token; effective per-token
  prices derived in the old table; `cache_read` is nominal.
- **oneprovider**: bills via credit multiplier — $25 top-up buys 8x value, so
  effective per-token price = catalog list x0.125. Both interpretations noted.
- **anymodel**: single flat rate per 1M tokens for input AND output
  (`flat_input_output`), derived from a 5¢ base x per-model multiplier.
- **unorouter**: shows discounted prices; original list price in `notes`.
- **openrouter**: negative prices (provider-subsidized routers like
  `openrouter/auto`) are skipped; `:batch` variants kept as separate records.
- **nano-gpt**: long-context input/output tiers (above 200k/272k) captured as
  `input_above_200k` / `output_above_200k`.

## Design decisions

- **JSONL, single file**: ~1.8k records, ~500KB — greppable, `jq`-able, no
  sharding needed. Sharding by provider or output_type would make cross-provider
  "who is cheapest for X" queries harder, which is the primary use case.
- **No OKF**: OKF (Google's Open Knowledge Format) is markdown+frontmatter for
  curated, human-maintained knowledge bundles with provenance/attestation. This
  dataset is machine-generated, refreshed wholesale from live sources, and
  queried with grep/jq — a flat JSONL with per-record `source.url` +
  `source.retrieved` gives the same provenance/freshness signals without the
  markdown ceremony. If this ever becomes a curated corpus with human review,
  OKF would be worth revisiting.
- **One record per provider variant** rather than one per model with nested
  provider prices: keeps records self-contained, trivially sortable by price,
  and free/paid variants stay explicit rows.
