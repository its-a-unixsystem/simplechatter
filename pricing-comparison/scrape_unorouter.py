#!/usr/bin/env python3
"""Scrape UnoRouter per-provider pages, extracting the embedded model JSON."""
import re
import json
import subprocess
import sys
import time

BASE = "https://unorouter.com/en/models"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"

PROVIDERS = [
    "agnes-ai", "ai-horde", "ai-singapore", "aion-labs", "alibaba", "anthropic",
    "baai", "bruhzwater", "bytedance", "codeium", "cohere", "deepseek",
    "dots-studio", "fallenmerick", "google", "groq", "inception", "jina-ai",
    "kinfra", "kuaishou", "liquid", "meganova", "meituan", "meta", "minimax",
    "mistral", "moonshot", "nex-agi", "nvidia", "openai", "perplexity",
    "poolside", "preferred-networks", "runware", "sao10k", "sarvam", "sdaia",
    "sensenova", "speakleash", "steelskull", "stepfun", "typhoon", "villanova",
    "xai", "xiaomi", "zhipu",
]

def fetch(url):
    r = subprocess.run(["curl", "-s", "-A", UA, url], capture_output=True, text=True)
    return r.stdout

def extract_models(raw):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', raw)
    # each chunk is a JSON string literal; json.loads handles \uXXXX and \\ safely
    # (unicode_escape would mangle non-latin1 chars and break the embedded JSON)
    parts = []
    for c in chunks:
        try:
            parts.append(json.loads('"' + c + '"'))
        except json.JSONDecodeError:
            continue
    blob = "".join(parts)
    # parse each embedded model object individually — whole-array bracket-walking
    # breaks when flight data splits model arrays across push chunks; model pages
    # also nest the object as {"model":{...}} so anchor on the key, not the brace
    dec = json.JSONDecoder()
    seen = {}
    for m in re.finditer(r'"model_name":', blob):
        # scan back to the opening '{' of the object containing this key
        i = m.start() - 1
        depth = 0
        while i >= 0:
            if blob[i] == "}":
                depth += 1
            elif blob[i] == "{":
                if depth == 0:
                    break
                depth -= 1
            i -= 1
        if i < 0:
            continue
        try:
            mod, _ = dec.raw_decode(blob, i)
        except json.JSONDecodeError:
            continue
        if isinstance(mod, dict) and "model_name" in mod:
            seen.setdefault(mod["model_name"], mod)
    return list(seen.values())

def main():
    all_models = []
    for p in PROVIDERS:
        raw = fetch(f"{BASE}/{p}")
        ms = extract_models(raw) if raw else []
        print(f"{p}: {len(ms)}", file=sys.stderr)
        for m in ms:
            m["provider_page"] = p
        all_models.extend(ms)
        time.sleep(0.15)
    # global dedupe (model can appear on multiple provider pages? model_name is global)
    seen = {}
    for m in all_models:
        seen.setdefault(m["model_name"], m)
    # completeness check against sitemap; fetch missing models from their own pages
    # (offline models are excluded from provider-page flight data but still listed in sitemap)
    sitemap = fetch("https://unorouter.com/sitemap.xml")
    sitemap_urls = [
        loc
        for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap)
        if re.match(r"https://unorouter\.com/en/models/[^/]+/[^/]+$", loc)
    ]
    missing = [u for u in sitemap_urls if u.rsplit("/", 1)[1] not in seen]
    for url in missing:
        mid = url.rsplit("/", 1)[1]
        raw = fetch(url)
        for m3 in extract_models(raw):
            seen.setdefault(m3["model_name"], m3)
        print(f"fallback {mid}: {'ok' if mid in seen else 'NOT FOUND'}", file=sys.stderr)
    with open("unorouter_raw.jsonl", "w") as f:
        for m in seen.values():
            f.write(json.dumps(m) + "\n")
    print(f"total unique {len(seen)} (sitemap: {len(sitemap_urls)})")

if __name__ == "__main__":
    main()
