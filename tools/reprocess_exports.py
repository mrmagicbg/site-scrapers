#!/usr/bin/env python3
"""Reprocess existing JSONL exports under exports/ by re-fetching each product URL
and running the updated extractor. This updates records in-place and regenerates
the combined printable HTML.

Usage: python3 tools/reprocess_exports.py
"""
from pathlib import Path
import json
import requests
from ebag_product_scraper.scraper import extract_product_info, load_html_from_url
from tools.generate_printable import load_jsonl, render_html, normalize_local_image_paths
import time


EXPORTS = Path("exports")


def reprocess_file(jpath: Path, delay: float = 0.5):
    print("Reprocessing", jpath)
    updated = []
    with jpath.open("r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        url = rec.get("url")
        if not url:
            updated.append(rec)
            continue
        try:
            html = load_html_from_url(url)
        except Exception as exc:
            print("  Failed to fetch", url, "->", exc)
            updated.append(rec)
            time.sleep(delay)
            continue
        try:
            info = extract_product_info(html)
        except Exception as exc:
            print("  Extract failed for", url, exc)
            updated.append(rec)
            time.sleep(delay)
            continue
        # merge preserving some existing fields like image_local/image_preview_local
        for k, v in info.items():
            rec[k] = v
        updated.append(rec)
        time.sleep(delay)

    # overwrite file
    with jpath.open("w", encoding="utf-8") as f:
        for r in updated:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(" Wrote", len(updated), "records to", jpath)
    return updated


def find_jsonl_files(base: Path):
    for p in base.rglob("*.jsonl"):
        # skip probes or examples directories
        if "/probes/" in str(p) or "/examples/" in str(p):
            continue
        yield p


def regenerate_combined(lang: str = 'bg'):
    from ebag_runner import main as runner_main  # reuse runner logic indirectly
    # simple regeneration: collect all per-category jsonl files under exports and render a combined HTML
    export_base = EXPORTS
    export_infos = []
    for jpath in export_base.rglob("*.jsonl"):
        if jpath.parent == export_base:
            continue
        label = jpath.parent.name
        display = label
        export_infos.append((display, label, jpath))

    combined_path = export_base / "combined_printable.html"
    sections = []
    header = render_html([], title=("Комбинирани продукти" if lang == 'bg' else "Combined products"), per_page=6, lang=lang)
    hidx = header.find("</header>")
    header_html = header[:hidx + len("</header>")] if hidx != -1 else header
    footer_html = header[header.rfind("</body>"):] if header.rfind("</body>") != -1 else "</body></html>"

    for display, label, jpath in export_infos:
        try:
            recs = load_jsonl(jpath)
            normalize_local_image_paths(recs, combined_path)
            cat_html = render_html(recs, title=display, per_page=6, lang=lang)
            h = cat_html.find("</header>")
            frag = cat_html[h + len("</header>"):] if h != -1 else cat_html
            fpos = frag.rfind("</body>")
            if fpos != -1:
                frag = frag[:fpos]
            section = f'<section class="category-block"><h2>{display}</h2>\n' + frag + "\n</section>"
            sections.append(section)
        except Exception as exc:
            print("  Failed to render section for", jpath, exc)

    if sections:
        final_html = header_html + "\n".join(sections) + footer_html
        combined_path.write_text(final_html, encoding="utf-8")
        print("Wrote combined printable HTML:", combined_path)
    else:
        print("No sections to include in combined printable")


def main():
    files = list(find_jsonl_files(EXPORTS))
    print("Found", len(files), "jsonl files to reprocess")
    total = 0
    for p in files:
        updated = reprocess_file(p)
        total += len(updated)
    print("Reprocessed total records:", total)
    regenerate_combined(lang='bg')


if __name__ == '__main__':
    main()
