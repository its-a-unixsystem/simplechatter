#!/usr/bin/env python3
"""Normalize all provider pricing data into a unified models.jsonl.

Output schema per line:
{
  "canonical": "claude-opus-4-8",            # sanitized canonical id
  "display_name": "Claude Opus 4.8",
  "vendor": "anthropic",
  "output_type": "text" | "image" | "video" | "audio" | "embedding",
  "free": false,                              # true for :free / $0 variants
  "context": 1000000,                          # context tokens, null if unknown
  "source": {
    "provider": "openrouter",
    "model_id": "anthropic/claude-opus-4.8",
    "url": "https://openrouter.ai/models",
    "retrieved": "2026-09-01"
  },
  "usd_per_1m": {                             # all optional
    "input": 5.0, "output": 25.0,
    "cache_read": 0.5, "cache_write": 6.25, "cache_write_1h": 10.0,
    "image": 0.1,                              # per generated image
    "input_audio": 1.0, "output_audio": 2.0
  },
  "notes": "..."                               # pricing caveats
}
"""
import json
import re
from datetime import date

TODAY = date.today().isoformat()

SOURCES = {
    "openrouter": "https://openrouter.ai/models",
    "unorouter": "https://unorouter.com/en/models",
    "raunai": "https://raunai.com/pricing",
    "oneprovider": "https://oneprovider.dev/pricing",
    "nano-gpt": "https://nano-gpt.com/pricing",
    "anymodel": "https://anymodel.org/en/models",
    "b.ai": "https://b.ai",  # from old local table
}

# ---------------------------------------------------------------------------
# Sanitization / canonical model-name translation
# ---------------------------------------------------------------------------

VENDOR_PATTERNS = [
    (r'\b(claude|anthropic)\b', 'anthropic'),
    (r'\b(gpt|openai|chatgpt|codex|o1|o3|o4)\b', 'openai'),
    (r'\b(gemini|google)\b', 'google'),
    (r'\bgrok\b', 'xai'),
    (r'\bglm\b', 'zhipu'),
    (r'\bdeepseek\b', 'deepseek'),
    (r'\bqwen\b', 'alibaba'),
    (r'\bkimi\b', 'moonshot'),
    (r'\bminimax\b', 'minimax'),
    (r'\bmistral\b', 'mistral'),
    (r'\bllama\b', 'meta'),
    (r'\bgranite\b', 'ibm'),
    (r'\bphi\b', 'microsoft'),
    (r'\bnemotron\b', 'nvidia'),
    (r'\bhunyuan\b', 'tencent'),
    (r'\bmimo\b', 'xiaomi'),
    (r'\bseedance\b', 'bytedance'),
    (r'\bflux\b', 'black-forest-labs'),
    (r'\bgpt-image\b', 'openai'),
    (r'\bwhisper\b', 'openai'),
]
ORG_PREFIXES = [
    'anthropic', 'openai', 'google', 'xai', 'z-ai', 'zai', 'zhipu', 'deepseek',
    'alibaba', 'qwen', 'moonshot', 'minimax', 'mistral', 'meta', 'ibm',
    'microsoft', 'nvidia', 'tencent', 'xiaomi', 'bytedance', 'perplexity',
    'meta-llama', 'openrouter', 'nousresearch', 'mistralai', 'qwenlm',
    'black-forest-labs', 'bfl', 'inclusionai', 'thinkingmachines',
]

def canonicalize(name: str) -> str:
    """Produce a canonical slug: lowercase, hyphens, version dots as dashes.

    Translation rules:
      claude-opus-4.8 / claude opus 4.8 / ClaudeOpus48 -> claude-opus-4-8
      vendor/org prefixes stripped (z-ai/glm-5.3-flash -> glm-5-3-flash)
      date suffixes stripped (claude-haiku-4-5-20251001 -> claude-haiku-4-5)
      :free markers stripped (free flag captured separately)
    """
    s = name.strip().lower()
    # strip :free / :variant suffix markers
    s = s.split(':')[0]
    # strip leading org prefix segments (a/b/c style ids)
    parts = s.split('/')
    while len(parts) > 1 and parts[0] in ORG_PREFIXES:
        parts = parts[1:]
    s = '/'.join(parts) if parts else s
    s = re.sub(r'[^a-z0-9.]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    # version dots: 4.8 -> 4-8 (digit.digit)
    s = re.sub(r'(\d)\.(\d)', r'\1-\2', s)
    # strip trailing date stamps like -20251001
    s = re.sub(r'-(\d{8})$', '', s)
    return s

def guess_vendor(canonical: str, model_id: str = '') -> str:
    hay = f"{canonical} {model_id.lower()}"
    for pat, vendor in VENDOR_PATTERNS:
        if re.search(pat, hay):
            return vendor
    return "unknown"

def new_rec(canonical, display, vendor, otype, free, ctx, provider, model_id, prices, notes=None):
    return {
        "canonical": canonical,
        "display_name": display,
        "vendor": vendor,
        "output_type": otype,
        "free": free,
        "context": ctx,
        "source": {
            "provider": provider,
            "model_id": model_id,
            "url": SOURCES[provider],
            "retrieved": TODAY,
        },
        "usd_per_1m": {k: v for k, v in prices.items() if v is not None},
        **({"notes": notes} if notes else {}),
    }

def parse_ctx(c):
    if c is None:
        return None
    if isinstance(c, (int, float)):
        return int(c)
    m = re.match(r'^([\d.]+)\s*([KM]?)$', str(c).strip())
    if not m:
        return None
    v = float(m.group(1))
    if m.group(2) == 'K':
        v *= 1_000
    elif m.group(2) == 'M':
        v *= 1_000_000
    return int(v)

# ---------------------------------------------------------------------------
# Provider parsers -> each yields records
# ---------------------------------------------------------------------------

def parse_openrouter(path):
    out = []
    for line in open(path):
        m = json.loads(line)
        mid = m['model_id']
        free = ':free' in mid
        base_id = mid[:-5] if free else mid
        canon = canonicalize(base_id)
        arch = m.get('architecture') or {}
        out_mods = arch.get('output_modalities') or []
        if 'image' in out_mods:
            otype = 'image'
        elif 'audio' in out_mods:
            otype = 'audio'
        elif 'video' in out_mods:
            otype = 'video'
        elif m.get('context_length') and 'embedding' in (mid + ' ' + (m.get('name') or '').lower()):
            otype = 'embedding'
        else:
            otype = 'text'
        p = m.get('pricing') or {}
        def fnum(k):
            v = p.get(k)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        # openrouter prices are per-token; convert to per-1M
        prices = {}
        for src, dst in [('prompt', 'input'), ('completion', 'output'),
                         ('input_cache_read', 'cache_read'),
                         ('input_cache_write', 'cache_write'),
                         ('input_cache_write_1h', 'cache_write_1h'),
                         ('image', 'image'),
                         ('audio', 'input_audio'),
                         ('audio_output', 'output_audio'),
                         ('image_output', 'image')]:
            v = fnum(src)
            if v is None:
                continue
            if v < 0:
                continue  # negative = provider-paid marker (openrouter/auto etc.)
            prices[dst] = round(v * 1_000_000, 6)
        if not prices and not free:
            # some models have zero prices (free without :free suffix)
            pass
        if free:
            prices = {}  # free variants: no per-token charge
        # name like "Anthropic: Claude Opus 4.8"
        disp = m.get('name') or base_id
        if ':' in disp:
            disp = disp.split(':', 1)[1].strip()
        out.append(new_rec(canon, disp, guess_vendor(canon, base_id), otype, free,
                           m.get('context_length'), 'openrouter', mid, prices))
    return out

def parse_unorouter(path):
    out = []
    for line in open(path):
        m = json.loads(line)
        name = m['model_name']
        free = bool(m.get('is_free')) or name.endswith(':free')
        base = name[:-5] if name.endswith(':free') else name
        canon = canonicalize(base)
        otype = m.get('type', 'text')
        meta = m.get('metadata') if isinstance(m.get('metadata'), dict) else {}
        prices = {}
        if not free:
            if m.get('input_price'):
                prices['input'] = round(m['input_price'], 6)
            if m.get('output_price'):
                prices['output'] = round(m['output_price'], 6)
            if m.get('is_fixed_price') and m.get('fixed_price'):
                prices = {'flat_per_request': m['fixed_price']}
        ctx = meta.get('contextWindow') or meta.get('maxInputTokens')
        # discount info
        oi, oo = m.get('original_input_price'), m.get('original_output_price')
        notes = None
        if oi and m.get('input_price') and oi > m['input_price']:
            notes = f"discounted from ${oi}/${oo} list"
        out.append(new_rec(canon, m.get('icon') and base or base, m.get('vendor', 'unknown').lower(),
                           otype, free, ctx, 'unorouter', name, prices, notes))
    return out

def parse_raunai(path):
    out = []
    for e in json.load(open(path)):
        canon = canonicalize(e['display_name'])
        r = e.get('rates') or {}
        prices = {}
        if r.get('input') is not None: prices['input'] = r['input']
        if r.get('output') is not None: prices['output'] = r['output']
        if r.get('cache_read'): prices['cache_read'] = r['cache_read']
        if r.get('cache_write'): prices['cache_write'] = r['cache_write']
        if e.get('per_image'): prices['image'] = e['per_image']
        otype = 'image' if e.get('per_image') and not prices.get('input') else 'text'
        free = prices.get('input') == 0 and prices.get('output') == 0
        out.append(new_rec(canon, e['display_name'], guess_vendor(canon), otype, free,
                           None, 'raunai', e['display_name'], prices))
    return out

def parse_oneprovider(path):
    out = []
    for m in json.load(open(path)):
        canon = canonicalize(m['model_id'])
        eff = m.get('effective_usd_per_1m') or {}
        prices = {}
        mapping = {'input': 'input', 'output': 'output', 'cache_read': 'cache_read',
                   'cache_write_5m': 'cache_write', 'cache_write_1h': 'cache_write_1h'}
        for k, v in mapping.items():
            if eff.get(k) is not None:
                prices[k] = eff[k]
        otype = 'image' if m['model_id'].startswith('gpt-image') else 'text'
        notes = ("effective prices = catalog list x0.125 (8x credit multiplier on top-ups); "
                 "see https://oneprovider.dev/docs/pricing/rates")
        out.append(new_rec(canon, m.get('display_name'), m.get('platform', 'unknown'), otype,
                           False, m.get('context_tokens'), 'oneprovider', m['model_id'], prices, notes))
    return out

def parse_nanogpt(path):
    out = []
    full = json.load(open('nano_full.json'))  # numeric per-million prices
    for cat, models in full['models'].items():
        for mid, m in models.items():
            canon = canonicalize(mid.split('/')[-1] if '/' in mid else mid)
            otype = cat
            prices = {}
            if cat == 'text':
                eff = (m.get('effective_pricing') or {}).get('effective_price') or {}
                inp = m.get('input_price_per_million')
                outp = m.get('output_price_per_million')
                if inp is not None:
                    prices['input'] = inp
                if outp is not None:
                    prices['output'] = outp
                cr = m.get('cacheReadInputPer1kTokens') or (m.get('pricing') or {}).get('cacheReadInputPer1kTokens')
                if cr is not None:
                    prices['cache_read'] = round(cr * 1000, 6)
                hi = eff.get('inputPer1kTokensAbove200k')
                ho = eff.get('outputPer1kTokensAbove200k')
                if hi is not None:
                    prices['input_above_200k'] = round(hi * 1000, 6)
                    prices['output_above_200k'] = round(ho * 1000, 6)
            elif cat == 'image':
                ci = m.get('cost') or {}
                vals = [v for v in ci.values() if isinstance(v, (int, float))]
                if vals:
                    prices['image'] = min(vals)
                    prices['image_max'] = max(vals)
            elif cat == 'video':
                p = m.get('pricing') or {}
                if p.get('input'):
                    prices['input'] = p['input']
                if p.get('output'):
                    prices['output'] = p['output']
            free = bool(prices) and all(v == 0 for v in prices.values() if isinstance(v, (int, float)))
            out.append(new_rec(canon, m.get('name') or mid, m.get('provider') or guess_vendor(canon, mid),
                               otype, free, m.get('maxInputTokens') or m.get('contextLength'), 'nano-gpt', mid, prices))
    return out

def parse_anymodel(path):
    out = []
    for m in json.load(open(path)):
        slug = m['model_slug'] or m['display_name']
        canon = canonicalize(slug.split('/')[-1] if '/' in slug else slug)
        flat = m.get('anymodel_usd_per_1m_flat')
        prices = {'flat_input_output': flat} if flat is not None else {}
        free = flat == 0
        notes = f"flat rate per 1M tokens for both input and output (base $0.05 x{m.get('multiplier')})"
        out.append(new_rec(canon, m.get('display_name'), m.get('vendor', 'unknown').lower(),
                           'text', free, parse_ctx(m.get('context')), 'anymodel', slug, prices, notes))
    return out

def parse_bai(path):
    out = []
    for e in json.load(open(path)):
        canon = canonicalize(e['display_name'])
        r = e.get('rates') or {}
        prices = {}
        if r.get('input') is not None: prices['input'] = r['input']
        if r.get('output') is not None: prices['output'] = r['output']
        if r.get('cache_read') is not None: prices['cache_read'] = r['cache_read']
        free = prices.get('input') == 0 and prices.get('output') == 0
        out.append(new_rec(canon, e['display_name'], guess_vendor(canon), 'text', free,
                           None, 'b.ai', e['display_name'], prices,
                           "b.ai subscription: $30/mo plan; cache_read is nominal (subscription doesn't bill cache separately)"))
    return out

# ---------------------------------------------------------------------------

def main():
    recs = []
    recs += parse_openrouter('openrouter_raw.jsonl')
    recs += parse_unorouter('unorouter_raw.jsonl')
    recs += parse_raunai('raunai_raw.json')
    recs += parse_oneprovider('oneprovider_raw.json')
    recs += parse_nanogpt('nanogpt_raw.jsonl')
    recs += parse_anymodel('anymodel_raw.json')
    recs += parse_bai('bai_raw.json')
    with open('models.jsonl', 'w') as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    from collections import Counter
    print('total records:', len(recs))
    print('by provider:', Counter(r['source']['provider'] for r in recs))
    print('by output_type:', Counter(r['output_type'] for r in recs))
    print('free variants:', sum(1 for r in recs if r['free']))

if __name__ == '__main__':
    main()
