#!/usr/bin/env python3
"""Query the normalized pricing dataset.

Usage:
  query.py <model-name>           # all providers, paid variants (default)
  query.py <model-name> --free    # only free variants
  query.py <model-name> --all     # free + paid
  query.py <model-name> --json    # raw jsonl lines

Model names are canonicalized the same way as the dataset
(claude-opus-4.8, claude opus 4.8, Claude Opus 4.8 all match).
"""
import argparse
import json
import sys
from normalize import canonicalize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('--free', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    canon = canonicalize(args.model)
    hits = []
    with open('models.jsonl') as f:
        for line in f:
            d = json.loads(line)
            if d['canonical'] != canon:
                continue
            if args.json:
                hits.append(d)
                continue
            if args.all or d['free'] == args.free:
                hits.append(d)

    if not hits:
        # substring fallback: 'opus 5' -> any canonical containing 'opus-5'
        sub = canon.replace(' ', '-')
        cands = {json.loads(l)['canonical'] for l in open('models.jsonl')}
        subs = sorted(c for c in cands if sub in c)
        if subs:
            print(f'no exact match for {canon!r}; substring matches: {", ".join(subs)}', file=sys.stderr)
            # family summary: cheapest paid input price per matched model
            import collections
            best = {}
            for line in open('models.jsonl'):
                d = json.loads(line)
                if d['canonical'] not in subs or d['free']:
                    continue
                p = d['usd_per_1m']
                inp = p.get('input') if p.get('input') is not None else p.get('flat_input_output')
                if inp is None:
                    continue
                cur = best.get(d['canonical'])
                if cur is None or inp < cur[0]:
                    best[d['canonical']] = (inp, d['source']['provider'])
            for c, (price, prov) in sorted(best.items()):
                print(f'  {c:40} from ${price}/1M in ({prov})')
            sys.exit(2)
        import difflib
        near = difflib.get_close_matches(canon, cands, n=5, cutoff=0.6)
        if near:
            print('did you mean:', ', '.join(near), file=sys.stderr)
        sys.exit(1)

    if args.json:
        for h in hits:
            print(json.dumps(h, ensure_ascii=False))
        return

    hits.sort(key=lambda h: h['source']['provider'])
    print(f'{canon}  ({"free" if args.free else "paid"} variants)' if not args.all else canon)
    hdr = (f"{'provider':12} {'variant':30} {'in $/1M':>9} {'out $/1M':>9} "
           f"{'cache_r':>8} {'flat/req':>8} {'$/image':>8}")
    print(hdr)
    print('-' * len(hdr))
    for h in hits:
        p = h['usd_per_1m']
        inp = p.get('input') if p.get('input') is not None else p.get('flat_input_output')
        outp = p.get('output') if p.get('output') is not None else p.get('flat_input_output')
        variant = h['source']['model_id'][:28]
        flat = p.get('flat_per_request')
        img = p.get('image')
        print(f"{h['source']['provider']:12} {variant:30} {str(inp):>9} {str(outp):>9} "
              f"{str(p.get('cache_read')):>8} {str(flat):>8} {str(img):>8}")
        if h.get('notes'):
            print(f"{'':12} note: {h['notes']}")


if __name__ == '__main__':
    main()
