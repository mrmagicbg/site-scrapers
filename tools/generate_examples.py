#!/usr/bin/env python3
from pathlib import Path
import json
from ebag_product_scraper.scraper import load_html_from_url, extract_product_info
from tools.generate_printable import load_jsonl

example_dirs = [
    'exports/categories_limon-i-laim_3646/categories_limon-i-laim_3646.jsonl',
    'exports/categories_gazirana-voda_568/categories_gazirana-voda_568.jsonl',
    'exports/categories_bial-bob_3821/categories_bial-bob_3821.jsonl',
]

out_dir = Path('exports/examples')
out_dir.mkdir(parents=True, exist_ok=True)

records = []
for p in example_dirs:
    jf = Path(p)
    if not jf.exists():
        continue
    recs = load_jsonl(jf)
    if not recs:
        continue
    url = recs[0]['url']
    html = load_html_from_url(url)
    info = extract_product_info(html)
    info['url'] = url
    records.append(info)

# simple HTML generation
for i, r in enumerate(records):
    fname = out_dir / f'example_{i+1}.html'
    parts = ['<!doctype html><html><meta charset="utf-8"><body>']
    parts.append(f"<h1>{r.get('name') or ''}</h1>")
    parts.append(f"<p>Цена: {r.get('price_amount') or r.get('price') or ''} {r.get('price_currency_bg') or ''}</p>")
    parts.append(f"<p>Код: {r.get('code') or ''}</p>")
    qraw = r.get('quantity_raw')
    qamt = r.get('quantity_amount')
    qunit = r.get('quantity_unit')
    qtot = r.get('quantity_total_amount')
    if qraw:
        parts.append(f"<p>Количество: {qraw}</p>")
    elif qamt and qunit:
        parts.append(f"<p>Количество: {qamt} {qunit}</p>")
    if qtot:
        parts.append(f"<p>Общо: {qtot} {r.get('quantity_total_unit') or ''}</p>")
    parts.append(f"<img src=\"{r.get('image') or ''}\" style=\"width:220px;height:220px;object-fit:cover\">")
    parts.append(f"<p><a href=\"{r.get('url')}\">оригинална страница</a></p>")
    parts.append('</body></html>')
    fname.write_text('\n'.join(parts), encoding='utf8')
    print('Wrote', fname)

if not records:
    print('No example records were generated (missing exports).')
