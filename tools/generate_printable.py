#!/usr/bin/env python3
"""Generate a printable HTML (and optional PDF) from a JSONL of product records.

Usage:
  python3 tools/generate_printable.py --input ebag_products_with_images.jsonl --output printable.html --pdf ebag_products.pdf --images-dir images2

The script will reference local preview images if present (`image_preview_local`), then `image_local`, then remote `image`.
If Playwright is installed, use --pdf to create a PDF ready for printing.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
import html
import os

def render_html(records, title: str = "Products", per_page: int = 6, lang: str = "en", format_type: str = "cards"):
    """Render HTML in either cards or table format."""
    if format_type == "table":
        return render_table_html(records, title, lang)
    else:
        return render_cards_html(records, title, per_page, lang)

def render_cards_html(records, title: str = "Products", per_page: int = 6, lang: str = "en"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    # simple translations
    translations = {
        "en": {"price": "Price", "code": "Code", "origin": "Origin", "generated": "Generated: {} — printable list ({})"},
        "bg": {"price": "Цена", "code": "Код", "origin": "Произход", "generated": "Генерирано: {} — списък за печат ({})"},
    }
    tr = translations.get(lang, translations["en"])
    parts = [
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\">",
        f"<title>{html.escape(title)}</title>",
        "<style>",
        "@page { size: A4; margin: 18mm; }",
        "body { font-family: Arial, Helvetica, sans-serif; color: #111; margin: 0; padding: 0; }",
        "header { text-align: center; margin-bottom: 8mm; }",
        "h1 { font-size: 20px; margin: 0 0 4px 0; }",
        "p.meta { font-size: 12px; margin: 0 0 12px 0; color: #444 }",
    ".grid { display: flex; flex-wrap: wrap; gap: 12px; }",
    # three cards per row: use ~33.333% minus gap compensation
    ".card { box-sizing: border-box; width: calc(33.333% - 8px); display:flex; gap:12px; padding:8px; border:1px solid #ddd; border-radius:6px; background:#fff; }",
    # slightly smaller image to fit three columns comfortably on A4
    ".card img { width:100px; height:100px; object-fit:cover; border-radius:4px; }",
        ".card .info { flex:1; display:flex; flex-direction:column; justify-content:space-between; }",
        ".card .name { font-size:14px; font-weight:600; margin-bottom:6px }",
        ".card .meta { font-size:12px; color:#333 }",
        ".small { font-size:11px; color:#666 }",
    "@media print { .card { width: calc(33.333% - 8px); } .no-print { display:none } }",
        "</style>",
        "</head><body>",
        "<header>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p class=\"meta\">{html.escape(tr['generated'].format(now, len(records)))}</p>",
        "</header>",
    ]

    for i, rec in enumerate(records):
        if i % per_page == 0:
            parts.append('<div class="page">')
        if i % per_page == 0:
            parts.append('<div class="grid">')

        # choose image
        img = rec.get("image_preview_local") or rec.get("image_local") or rec.get("image") or ""
        # make a relative path if local
        if img and img.startswith('/'):
            img = img[1:]
        name = rec.get("name") or ""
        # prefer structured price amount + localized currency when available
        price_amount = rec.get("price_amount") or ""
        price_curr = rec.get("price_currency_bg") or ""
        price_fallback = rec.get("price") or ""
        # build display price: use amount+currency if available, else fallback
        if price_amount and price_curr:
            price_display = f"{price_amount} {price_curr}"
        elif price_amount:
            price_display = str(price_amount)
        else:
            price_display = str(price_fallback)

        code = rec.get("code") or ""
        # quantity info
        q_amt = rec.get("quantity_amount")
        q_unit = rec.get("quantity_unit")
        q_raw = rec.get("quantity_raw")
        q_total = rec.get("quantity_total_amount")
        q_total_unit = rec.get("quantity_total_unit")
        # translations for quantity and total
        qty_label = "Количество" if lang == 'bg' else "Quantity"
        total_label = "Общо" if lang == 'bg' else "Total"

        qty_parts = []
        if q_raw:
            qty_parts.append(str(q_raw))
        elif q_amt and q_unit:
            qty_parts.append(f"{q_amt} {q_unit}")
        if q_total and q_total_unit:
            qty_parts.append(f"{total_label}: {q_total} {q_total_unit}")
        qty_display = ' — '.join(qty_parts) if qty_parts else ''

        card = f'''<article class="card"><img src="{html.escape(img)}" alt=""><div class="info"><div><div class="name">{html.escape(name)}</div><div class="meta">{html.escape(tr['price'])}: {html.escape(price_display)}</div><div class="small">{html.escape(tr['code'])}: {html.escape(str(code))}</div>''' \
               + (f"<div class=\"small\">{html.escape(qty_label)}: {html.escape(qty_display)}</div>" if qty_display else "") \
               + "</div></div></article>"
        parts.append(card)

        if (i + 1) % per_page == 0 or i == len(records) - 1:
            parts.append('</div>')
            parts.append('</div>')

    parts.append('</body></html>')
    return '\n'.join(parts)

def render_table_html(records, title: str = "Products", lang: str = "en"):
    """Render HTML in table format with 10 columns for printer scaling."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    translations = {
        "en": {"price": "Price", "code": "Code", "generated": "Generated: {} — printable table ({} products)"},
        "bg": {"price": "Цена", "code": "Код", "generated": "Генерирано: {} — таблица за печат ({} продукта)"},
    }
    tr = translations.get(lang, translations["en"])
    
    # Group records by category for organized display
    categories = {}
    current_category = "Некатегоризирани" if lang == "bg" else "Uncategorized"
    
    for rec in records:
        # Try to extract category from URL or use current category
        url = rec.get("url", "")
        if "/categories/" in url:
            # Extract category from eBag URL structure
            try:
                cat_part = url.split("/categories/")[1].split("/")[0]
                # Convert category slug to display name
                cat_name = cat_part.replace("-", " ").title()
                current_category = cat_name
            except:
                pass
        
        if current_category not in categories:
            categories[current_category] = []
        categories[current_category].append(rec)
    
    # Start HTML
    parts = [
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\">",
        f"<title>{html.escape(title)}</title>",
        "<style>",
        "@page { size: A4 landscape; margin: 10mm; }",
        "body { font-family: Arial, sans-serif; font-size: 9px; margin: 0; padding: 0; }",
        "header { text-align: center; margin-bottom: 5mm; }",
        "h1 { font-size: 16px; margin: 0 0 2px 0; }",
        "p.meta { font-size: 10px; margin: 0 0 8px 0; color: #666; }",
        "h2 { font-size: 12px; margin: 8px 0 4px 0; color: #333; page-break-inside: avoid; }",
        "table { width: 100%; border-collapse: collapse; margin-bottom: 8px; page-break-inside: avoid; }",
        "td { width: 10%; padding: 2px; border: 1px solid #ddd; vertical-align: top; text-align: center; }",
        "td img { width: 30px; height: 30px; object-fit: cover; display: block; margin: 0 auto 2px auto; }",
        ".product-name { font-weight: bold; font-size: 8px; margin-bottom: 1px; line-height: 1.1; }",
        ".product-price { color: #d63384; font-weight: bold; font-size: 8px; margin-bottom: 1px; }",
        ".product-qty { color: #666; font-size: 7px; margin-bottom: 1px; }",
        ".product-code { color: #666; font-size: 7px; }",
        "@media print { body { font-size: 8px; } h1 { font-size: 14px; } h2 { font-size: 11px; } }",
        "</style>",
        "</head><body>",
        "<header>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p class=\"meta\">{html.escape(tr['generated'].format(now, len(records)))}</p>",
        "</header>",
    ]
    
    for category_name, category_records in categories.items():
        if not category_records:
            continue
            
        parts.append(f"<h2>{html.escape(category_name)}</h2>")
        
        # Create table with 10 columns
        for i in range(0, len(category_records), 10):
            parts.append("<table>")
            parts.append("<tr>")
            
            row_records = category_records[i:i+10]
            for rec in row_records:
                # Get product info
                img = rec.get("image_preview_local") or rec.get("image_local") or rec.get("image") or ""
                if img and img.startswith('/'):
                    img = img[1:]
                name = rec.get("name") or ""
                price_amount = rec.get("price_amount") or ""
                price_curr = rec.get("price_currency_bg") or ""
                price_fallback = rec.get("price") or ""
                
                if price_amount and price_curr:
                    price_display = f"{price_amount} {price_curr}"
                elif price_amount:
                    price_display = str(price_amount)
                else:
                    price_display = str(price_fallback)
                
                code = rec.get("code") or ""
                
                # Get quantity info (matching the cards format logic)
                q_amt = rec.get("quantity_amount")
                q_unit = rec.get("quantity_unit")
                q_raw = rec.get("quantity_raw")
                q_total = rec.get("quantity_total_amount")
                q_total_unit = rec.get("quantity_total_unit")
                # translations for quantity and total
                qty_label = "Количество" if lang == 'bg' else "Quantity"
                total_label = "Общо" if lang == 'bg' else "Total"

                qty_parts = []
                if q_raw:
                    qty_parts.append(str(q_raw))
                elif q_amt and q_unit:
                    qty_parts.append(f"{q_amt} {q_unit}")
                if q_total and q_total_unit:
                    qty_parts.append(f"{total_label}: {q_total} {q_total_unit}")
                qty_display = ' — '.join(qty_parts) if qty_parts else ''
                
                # Create table cell with quantity
                qty_html = f'<div class="product-qty">{html.escape(qty_display)}</div>' if qty_display else ''
                cell_html = f'''<td>
                    <img src="{html.escape(img)}" alt="">
                    <div class="product-name">{html.escape(name)}</div>
                    <div class="product-price">{html.escape(price_display)}</div>
                    {qty_html}
                    <div class="product-code">{html.escape(str(code))}</div>
                </td>'''
                parts.append(cell_html)
            
            # Fill empty cells if row is not complete
            for _ in range(10 - len(row_records)):
                parts.append("<td></td>")
            
            parts.append("</tr>")
            parts.append("</table>")
    
    parts.append("</body></html>")
    return '\n'.join(parts)

def load_jsonl(path: Path):
    recs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            recs.append(json.loads(line))
    return recs


def normalize_local_image_paths(recs: list[dict], output_html_path: Path):
    """Make local image paths relative to the output HTML file location.

    This mutates the recs in-place and returns them for convenience.
    """
    out_dir = output_html_path.parent.resolve()
    for r in recs:
        for k in ("image_preview_local", "image_local"):
            v = r.get(k)
            if not v:
                continue
            pth = Path(v)
            try:
                if not pth.is_absolute():
                    pth = (Path.cwd() / pth).resolve()
                else:
                    pth = pth.resolve()
            except Exception:
                continue
            try:
                rel = Path(os.path.relpath(str(pth), start=str(out_dir)))
                r[k] = str(rel.as_posix())
            except Exception:
                r[k] = str(pth)
    return recs

def main(argv=None):
    p = argparse.ArgumentParser(description="Generate printable HTML (and PDF) from JSONL product records")
    p.add_argument("--input", required=True, help="JSONL input file")
    p.add_argument("--output", required=True, help="HTML output file")
    p.add_argument("--pdf", help="Optional PDF output file (requires Playwright)")
    p.add_argument("--images-dir", help="Optional base dir to make local image paths relative when embedding")
    p.add_argument("--lang", choices=["en", "bg"], default="en", help="Language for labels (en or bg)")
    p.add_argument("--per-page", type=int, default=6, help="Number of product cards per page (cards format only)")
    p.add_argument("--format", choices=["cards", "table"], default="cards", help="Output format: cards (default) or table")
    args = p.parse_args(argv)

    src = Path(args.input)
    out = Path(args.output)
    recs = load_jsonl(src)

    # Normalize image paths so the generated HTML references images relative to the
    # output file. This ensures image src work when opening the HTML via file://
    normalize_local_image_paths(recs, out)

    html_out = render_html(recs, title="eBag products", per_page=args.per_page, lang=args.lang, format_type=args.format)
    out.write_text(html_out, encoding="utf-8")
    print("Wrote", out)

    if args.pdf:
        # try to render a PDF using Playwright if available
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            print("Playwright not available; skipping PDF generation")
            return
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto('file://' + str(out.resolve()))
            # give images a moment
            page.wait_for_timeout(500)
            page.pdf(path=args.pdf, format='A4', print_background=True)
            browser.close()
        print("Wrote PDF", args.pdf)

if __name__ == '__main__':
    main()
