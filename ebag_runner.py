#!/usr/bin/env python3
"""Runner script to fetch product pages (e.g. from ebag.bg) and extract product info.

Usage examples:
  # single URL -> JSONL to stdout
  python3 ebag_runner.py --url "https://www.ebag.bg/.." --output -

  # multiple URLs from file -> CSV
  python3 ebag_runner.py --input urls.txt --output results.csv --format csv --delay 1.5

This script respects a small delay between requests and retries on transient errors.
"""

from __future__ import annotations
import argparse
import csv
import json
import time
from typing import Iterable

import requests
import os
import io
from pathlib import Path

from ebag_product_scraper.scraper import extract_product_info
try:
    from bs4 import BeautifulSoup  # type: ignore
    BS4_AVAILABLE = True
except Exception:
    BeautifulSoup = None
    BS4_AVAILABLE = False
import re
from urllib.parse import urljoin, urlparse
import html as html_module
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    Image = None
    PIL_AVAILABLE = False


DEFAULT_PRODUCT_LINK_SELECTORS = [
    "a.product-card__link",
    "a.card-product__link",
    "a.product-link",
    "a[href*='/product']",
    "a[href*='/products']",
    "a[href*='/p/']",
    "a[href*='/catalog/']",
]


DEFAULT_USER_AGENT = "site-scrapers/0.1 (+https://github.com/ivan-madjarov)"


def fetch_html(url: str, session: requests.Session, retries: int = 3, timeout: int = 10, delay: float = 1.0) -> str:
    last_exc = None
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(delay * attempt)
            else:
                raise


def iterate_urls_from_file(path: str) -> Iterable[str]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield line


def extract_product_links_from_category(html: str, base_url: str) -> list[str]:
    links = []
    if BS4_AVAILABLE and BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        # First: common selectors (kept for other sites)
        for sel in DEFAULT_PRODUCT_LINK_SELECTORS:
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                abs_url = urljoin(base_url, href)
                links.append(abs_url)

        # eBag specific: many product links are anchors inside article elements
        # with hrefs like "/some-slug/589150?..." (slug + numeric id). Prefer
        # those to avoid picking up policy/documentation links.
        product_href_re = re.compile(r"/[^/]+/\d+(/|$|\?)")
        for article in soup.find_all("article"):
            a = article.find("a", href=True)
            if a:
                href = a["href"]
                if href and product_href_re.search(href):
                    links.append(urljoin(base_url, href))

        # If still empty, try a broader scan for anchors whose href matches
        # a slug/number pattern or contains known product tokens.
        if not links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href:
                    continue
                if product_href_re.search(href) or any(tok in href for tok in ("/product", "/products", "/item", "/p/", "/catalog/", "/product-")):
                    links.append(urljoin(base_url, href))
    else:
        # regex fallback: find href attributes with likely product paths
        # look for slug/number patterns as in ebag (e.g. /slug/12345)
        for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
            href = m.group(1)
            if re.search(r"/[^/]+/\d+(/|$|\?)", href) or any(tok in href for tok in ("/product", "/products", "/item", "/p/", "/catalog/", "/product-")):
                links.append(urljoin(base_url, href))

    # dedupe while preserving order and strongly filter to product-like URLs
    seen = set()
    out = []
    # blacklist fragments that indicate non-product pages
    blacklist = ("/product-replacement-policy", "/privacy", "/terms", "/cookies", "/pages/", "/faq", "/contacts", "/delivery", "/categories/")
    product_like_re = re.compile(r"/[^/]+/\d+(/|$|\?)")

    for u in links:
        # normalize path-only links
        # normalize mobile subdomain to canonical host to avoid duplicates
        try:
            pu = urlparse(u)
            # convert m.ebag.bg -> www.ebag.bg
            if pu.netloc.startswith("m."):
                pu = pu._replace(netloc=pu.netloc.replace("m.", "www."))
                u = pu.geturl()
        except Exception:
            pass

        if u in seen:
            continue
        # skip obvious site pages
        if any(tok in u for tok in blacklist):
            continue
        # (do not aggressively drop links here beyond blacklist; keep product-like filtering below)
        # accept only if it matches slug + numeric id pattern or contains /product(s)/ or /p/
        if product_like_re.search(u) or any(tok in u for tok in ("/product/", "/products/", "/p/", "/products/images/")):
            seen.add(u)
            out.append(u)
    return out


def find_next_page_link(html: str, base_url: str) -> str | None:
    if BS4_AVAILABLE and BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        # common patterns
        a = soup.find("a", rel="next")
        if a and a.get("href"):
            return urljoin(base_url, a["href"])

        # look for link with text 'Следваща' (Bulgarian) or common classes
        for text in ("Следваща", "Next", "Следната"):
            a = soup.find(lambda tag: tag.name == "a" and tag.get_text(strip=True) == text)
            if a and a.get("href"):
                return urljoin(base_url, a["href"])

        # pagination next class
        for cls in ("pagination-next", "pager-next", "next"):
            a = soup.find("a", class_=cls)
            if a and a.get("href"):
                return urljoin(base_url, a["href"])

        return None
    else:
        # regex fallback: look for rel="next" or common next links
        m = re.search(r'rel=["\']next["\']\s+href=["\']([^"\']+)["\']', html, re.I)
        if m:
            return urljoin(base_url, m.group(1))
        m = re.search(r'href=["\']([^"\']+)["\'][^>]*>\s*(Следваща|Next|Следната)\s*<', html, re.I)
        if m:
            return urljoin(base_url, m.group(1))
        m = re.search(r'href=["\']([^"\']+page=[0-9]+[^"\']*)["\']', html, re.I)
        if m:
            return urljoin(base_url, m.group(1))
        return None


def process_urls(urls: Iterable[str], out_path: str | None, out_format: str = "jsonl", delay: float = 1.0, images_dir: str | None = None, thumb_size: int = 200):
    session = requests.Session()
    results = []
    writer_csv = None
    # Open CSV file early; use try/finally to guarantee it is closed even on error.
    csv_file = open(out_path, "w", newline="", encoding="utf-8") if (out_path and out_format == "csv") else None

    def write_record(record: dict):
        if out_path is None or out_path == "-":
            if out_format == "jsonl":
                print(json.dumps(record, ensure_ascii=False))
            else:
                # fallback to json
                print(json.dumps(record, ensure_ascii=False))
            return

        if out_format == "jsonl":
            with open(out_path, "a", encoding="utf-8") as o:
                o.write(json.dumps(record, ensure_ascii=False) + "\n")
        elif out_format == "csv":
            nonlocal writer_csv, csv_file
            if writer_csv is None:
                # create CSV writer with headers from keys
                fieldnames = list(record.keys())
                writer_csv = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer_csv.writeheader()
            writer_csv.writerow(record)

    try:
        for url in urls:
            try:
                # Hybrid approach: Try fast HTTP first, fallback to Playwright if quantity missing
                html = fetch_html(url, session, delay=delay)
                info = extract_product_info(html)

                # If no quantity found with basic HTTP, try Playwright for JavaScript-rendered content
                if not info.get('quantity_raw'):
                    try:
                        from ebag_product_scraper.scraper import load_html_from_url
                        html = load_html_from_url(url)
                        info = extract_product_info(html)
                    except Exception:
                        # If Playwright fails, keep the basic HTTP results
                        pass
            except Exception as exc:
                record = {"url": url, "error": str(exc)}
                write_record(record)
                continue
            record = {"url": url, **info}
            # optionally download image and create a thumbnail if requested via CLI arg
            imgs_dir = images_dir
            if imgs_dir and info.get("image"):
                try:
                    img_url = info.get("image")
                    # sanitize filename
                    parsed = urlparse(img_url)
                    orig_name = Path(parsed.path).name
                    target_dir = Path(imgs_dir)
                    target_dir.mkdir(parents=True, exist_ok=True)
                    # determine extension: prefer existing extension, otherwise infer from content-type
                    ext = Path(orig_name).suffix
                    r = session.get(img_url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=15)
                    r.raise_for_status()
                    if not ext:
                        ctype = r.headers.get("Content-Type", "")
                        if "jpeg" in ctype or "jpg" in ctype:
                            ext = ".jpg"
                        elif "png" in ctype:
                            ext = ".png"
                        elif "webp" in ctype:
                            ext = ".webp"
                        else:
                            ext = ".jpg"
                    # prefer using product code for filename to avoid collisions
                    codefn = info.get("code") or None
                    if codefn:
                        filename = f"{codefn}{ext}"
                    else:
                        filename = orig_name + ext if not Path(orig_name).suffix else orig_name
                    img_path = target_dir / filename
                    # write image to disk
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                    record["image_local"] = str(img_path)
                    # create thumbnail preview
                    if PIL_AVAILABLE:
                        try:
                            with Image.open(io.BytesIO(r.content)) as im:
                                im.thumbnail((thumb_size, thumb_size))
                                preview_name = img_path.stem + "_preview" + img_path.suffix
                                preview_path = target_dir / preview_name
                                # infer format from extension
                                fmt = None
                                sfx = img_path.suffix.lower()
                                if sfx in (".jpg", ".jpeg"):
                                    fmt = "JPEG"
                                elif sfx == ".png":
                                    fmt = "PNG"
                                elif sfx == ".webp":
                                    fmt = "WEBP"
                                im.save(preview_path, format=fmt) if fmt else im.save(preview_path)
                                record["image_preview_local"] = str(preview_path)
                        except Exception:
                            # continue without preview
                            pass
                except Exception as exc:
                    record["image_error"] = str(exc)
            write_record(record)
            time.sleep(delay)
    finally:
        # Guarantee CSV file is flushed and closed even if an unhandled exception occurs
        if csv_file:
            csv_file.close()


def render_page_with_playwright(url: str, timeout: int = 30) -> str:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright is not installed")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=timeout * 1000)
        # wait for network to be idle briefly
        page.wait_for_timeout(1000)
        content = page.content()
        browser.close()
        return content


def main(argv=None):
    p = argparse.ArgumentParser(description="Fetch product pages and extract product info (ebag.bg)")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Single product URL to fetch")
    group.add_argument("--input", help="File with product URLs (one per line)")
    group.add_argument("--category", help="Category URL to crawl for product links (e.g. https://www.ebag.bg/categories/plodove/600)")
    group.add_argument("--categories-file", help="File with category URLs (one per line). Each category will be crawled separately when provided")
    p.add_argument("--output", "-o", default="-", help="Output path or '-' for stdout (default '-')")
    p.add_argument("--format", choices=("jsonl", "csv"), default="jsonl", help="Output format")
    p.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between requests")
    p.add_argument("--retries", type=int, default=3, help="Number of retries for HTTP requests")
    p.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds")
    # Render pages with Playwright by default when available. Provide a
    # --no-render flag to disable rendering if desired.
    p.add_argument("--no-render", action="store_false", dest="render", default=True, help="Disable Playwright rendering before parsing (default: enabled when Playwright is installed)")
    p.add_argument("--images-dir", help="Directory to save downloaded images and previews (optional)")
    p.add_argument("--thumb-size", type=int, default=200, help="Max size (px) for thumbnail previews")
    # auto-export: when enabled (default), outputs and images will be placed under exports/<label>/
    p.add_argument("--no-auto-export", action="store_false", dest="auto_export", help="Disable automatic exports under exports/ (default enabled)")
    # auto-download images and auto-generate printable HTML by default; provide flags to disable
    p.add_argument("--no-download-images", action="store_false", dest="download_images", help="Disable automatic image downloads (default enabled)")
    p.add_argument("--no-auto-html", action="store_false", dest="auto_html", help="Disable automatic printable HTML export (default enabled)")
    p.add_argument("--html-lang", choices=("en","bg"), default="bg", help="Language for auto-generated printable HTML (default: bg)")
    p.add_argument("--html-format", choices=("cards","table"), default="cards", help="Format for auto-generated printable HTML: cards (default) or table")
    p.add_argument("--no-combined", action="store_false", dest="combined", help="Do not create a single combined printable HTML; produce per-category printable.html instead (default: create combined)")
    args = p.parse_args(argv)

    # Informative warning when user requested rendering but Playwright isn't available
    if getattr(args, 'render', True) and not PLAYWRIGHT_AVAILABLE:
        print("Warning: Playwright is not installed in this Python environment. "
              "Category pages will be fetched without rendering. "
              "Run the script with the project's virtualenv Python or install Playwright and browsers to enable rendering.")

    # If user provided a categories file, process each category separately and
    # create per-category export dirs when auto_export is enabled.
    if args.categories_file:
        categories = list(iterate_urls_from_file(args.categories_file))
    else:
        categories = [args.category] if args.category else []

    # If auto-export is enabled (default), start with a clean exports/ directory
    # so each run produces fresh outputs. This avoids appending to previous
    # results unexpectedly. BUT: Don't clean when processing multiple categories!
    if getattr(args, "auto_export", True) and not args.categories_file:
        try:
            export_base = Path("exports")
            if export_base.exists():
                # remove the directory tree
                import shutil

                shutil.rmtree(export_base)
            export_base.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            print("Warning: failed to clean exports/ directory:", exc)

    if args.url:
        # single product URL: just process it and exit
        urls = [args.url]
        # determine export locations when auto_export is enabled (default behavior)
        auto_export = getattr(args, "auto_export", True)
        export_base = Path("exports")
        out_path = None if args.output == "-" else args.output
        images_dir = args.images_dir
        download_images = getattr(args, "download_images", True)
        auto_html = getattr(args, "auto_html", True)
        # derive label from URL
        parsed = urlparse(args.url)
        parts = [p for p in parsed.path.split("/") if p]
        slug = parts[-1] if parts else parsed.netloc
        label = re.sub(r"\s+", "_", slug)
        label = re.sub(r"[^A-Za-z0-9_\-]+", "", label)[:120]
        export_dir = export_base / label
        export_dir.mkdir(parents=True, exist_ok=True)
        if out_path is None:
            out_path = str(export_dir / f"{label}.{args.format}")
        if images_dir is None and download_images:
            images_dir = str(export_dir / "images")
        process_urls(urls, out_path=(None if out_path == "-" else out_path), out_format=args.format, delay=args.delay, images_dir=images_dir, thumb_size=args.thumb_size)
        return

    if args.input:
        urls = list(iterate_urls_from_file(args.input))
        # single batch of URLs from input file: use existing auto_export logic below
    elif categories:
        # process each category separately
        session = requests.Session()
        auto_export = getattr(args, "auto_export", True)
        export_base = Path("exports")
        download_images = getattr(args, "download_images", True)
        auto_html = getattr(args, "auto_html", True)
        export_infos = []
        for cat in categories:
            urls = []
            next_page = cat
            pages = 0
            # attempt to capture a human-friendly category title (prefer H1 then <title>)
            cat_title = None
            # Follow pages until there is no 'next' link. Rendering is used by default
            # (unless user passes --no-render). This ensures we collect all product links
            # across the category pagination.
            while next_page:
                try:
                    if args.render and PLAYWRIGHT_AVAILABLE:
                        try:
                            html = render_page_with_playwright(next_page, timeout=args.timeout)
                        except Exception:
                            # fallback to non-rendered fetch on render failure
                            html = fetch_html(next_page, session, delay=args.delay)
                    else:
                        html = fetch_html(next_page, session, delay=args.delay)
                    # try to extract a category title from the first page fetched
                    if not cat_title and BS4_AVAILABLE and BeautifulSoup is not None:
                        try:
                            soup = BeautifulSoup(html, "html.parser")
                            # prefer H1
                            h1 = soup.find("h1")
                            if h1 and h1.get_text(strip=True):
                                cat_title = h1.get_text(strip=True)
                            else:
                                # common page-title classes
                                pt = soup.find(class_=re.compile(r"page-?title|title|category-title", re.I))
                                if pt and pt.get_text(strip=True):
                                    cat_title = pt.get_text(strip=True)
                                else:
                                    # open graph title meta
                                    og = soup.find("meta", property="og:title")
                                    if og and og.get("content"):
                                        cat_title = og.get("content").strip()
                                    else:
                                        tit = soup.find("title")
                                        if tit and tit.get_text(strip=True):
                                            cat_title = tit.get_text(strip=True)
                        except Exception:
                            pass
                except Exception as exc:
                    print(f"Failed to fetch category page {next_page}: {exc}")
                    break
                links = extract_product_links_from_category(html, next_page)
                # If the initial fetch was non-rendered (either because rendering was
                # disabled or Playwright wasn't available), attempt a rendered fetch
                # as a fallback when Playwright is available. This can reveal JS-populated
                # product lists on some category pages.
                if not (args.render and PLAYWRIGHT_AVAILABLE) and PLAYWRIGHT_AVAILABLE:
                    try:
                        html_r = render_page_with_playwright(next_page, timeout=args.timeout)
                        links_r = extract_product_links_from_category(html_r, next_page)
                        if len(links_r) > len(links):
                            links = links_r
                    except Exception:
                        # ignore render fallback failures and use original links
                        pass
                for l in links:
                    if l not in urls:
                        urls.append(l)
                next_page = find_next_page_link(html, next_page)
                pages += 1
                time.sleep(args.delay)

            # prepare export dir for this category when auto_export is enabled
            label = None
            images_dir = args.images_dir
            out_path = None if args.output == "-" else args.output
            if auto_export:
                parsed = urlparse(cat)
                cat_path = parsed.path.strip("/") or parsed.netloc
                label = re.sub(r"\s+", "_", cat_path.replace("/", "_"))
                label = re.sub(r"[^A-Za-z0-9_\-]+", "", label)[:120]
                export_dir = export_base / label
                export_dir.mkdir(parents=True, exist_ok=True)
                if out_path is None:
                    out_path = str(export_dir / f"{label}.{args.format}")
                if images_dir is None and download_images:
                    images_dir = str(export_dir / "images")

            print(f"Collected {len(urls)} product links from category {cat}")
            # run the processor for this category
            process_urls(urls, out_path=(None if out_path == "-" else out_path), out_format=args.format, delay=args.delay, images_dir=images_dir, thumb_size=args.thumb_size)

            # remember what we wrote for later combined HTML
            if auto_export and out_path and args.format == "jsonl":
                try:
                    display = cat_title or label
                    # prefer Bulgarian-friendly title when present; fallback to label
                    export_infos.append((display, label, Path(out_path)))
                except Exception:
                    pass

            # optionally auto-generate printable HTML per-category (only if combined is disabled)
            if not args.combined and auto_export and auto_html and out_path and args.format == "jsonl":
                try:
                    from tools.generate_printable import load_jsonl, render_html, normalize_local_image_paths
                    jpath = Path(out_path)
                    if jpath.exists():
                        records = load_jsonl(jpath)
                        ph = export_dir / "printable.html"
                        try:
                            normalize_local_image_paths(records, ph)
                        except Exception:
                            pass
                        html_content = render_html(records, title=label if label else 'products', per_page=6, lang=args.html_lang, format_type=args.html_format)
                        ph.write_text(html_content, encoding="utf-8")
                        print("Wrote printable HTML:", ph)
                except Exception as exc:
                    print("Failed to auto-generate printable HTML:", exc)
            # end of per-category processing loop iteration
    # After processing all categories, optionally produce a single combined
        # printable HTML that includes all per-category exports. This should run
        # once, after the loop, and only when auto_export + auto_html are enabled
        # and the user didn't opt-out via --no-combined.
        if auto_export and auto_html and getattr(args, 'combined', True) and args.format == 'jsonl' and export_infos:
            try:
                from tools.generate_printable import load_jsonl, render_html, normalize_local_image_paths
                combined_path = export_base / "combined_printable.html"
                # Prepare header/footer from an empty render to preserve CSS/structure
                combined_title = "Комбинирани продукти" if args.html_lang == 'bg' else "Combined products"
                base = render_html([], title=combined_title, per_page=6, lang=args.html_lang, format_type=args.html_format)
                header_end_idx = base.find("</header>")
                if header_end_idx != -1:
                    header_end_idx += len("</header>")
                else:
                    header_end_idx = 0
                footer_start_idx = base.rfind("</body>")
                header_html = base[:header_end_idx]
                footer_html = base[footer_start_idx:] if footer_start_idx != -1 else "</body></html>"

                combined_sections = []
                for display, label, jpath in export_infos:
                    print(f"Processing export: label={label} path={jpath}")
                    try:
                        if not jpath.exists():
                            print(f"  Skipping missing file: {jpath}")
                            continue
                        records = load_jsonl(jpath)
                        # normalize local paths relative to the combined output
                        try:
                            normalize_local_image_paths(records, combined_path)
                        except Exception as e:
                            print("  Warning: normalize_local_image_paths failed:", e)
                        # use the captured display title (often Bulgarian) for the section
                        cat_html = render_html(records, title=display or label, per_page=6, lang=args.html_lang, format_type=args.html_format)
                        # extract body fragment after header and before footer
                        hidx = cat_html.find("</header>")
                        frag = cat_html[hidx + len("</header>"): ] if hidx != -1 else cat_html
                        # strip trailing closing tags if present
                        fpos = frag.rfind("</body>")
                        if fpos != -1:
                            frag = frag[:fpos]
                        section = f'<section class="category-block"><h2>{html_module.escape(display)}</h2>\n' + frag + "\n</section>"
                        combined_sections.append(section)
                    except Exception as exc:
                        print(f"  Error processing {jpath}: {exc}")
                        continue

                if combined_sections:
                    final_html = header_html + "\n".join(combined_sections) + footer_html
                    combined_path.write_text(final_html, encoding="utf-8")
                    print("Wrote combined printable HTML:", combined_path)
                else:
                    # write a minimal combined file so users see the header even when no sections succeeded
                    fallback_body = "<p>Няма намерени продукти</p>" if args.html_lang == 'bg' else "<p>No products found</p>"
                    final_html = header_html + fallback_body + footer_html
                    combined_path.write_text(final_html, encoding="utf-8")
                    print("Wrote empty combined printable HTML (no sections):", combined_path)
            except Exception as exc:
                print("Failed to generate combined printable HTML:", exc)
    else:
        raise SystemExit("one of --url, --input or --category or --categories-file is required")

    # determine export locations when auto_export is enabled (default behavior)
    auto_export = getattr(args, "auto_export", True)
    export_base = Path("exports")
    out_path = None if args.output == "-" else args.output
    images_dir = args.images_dir
    download_images = getattr(args, "download_images", True)
    auto_html = getattr(args, "auto_html", True)

    def sanitize_label(s: str) -> str:
        # make a filesystem-safe short label
        s = s.strip()
        s = re.sub(r"\s+", "_", s)
        s = re.sub(r"[^A-Za-z0-9_\-]+", "", s)
        return s[:120]

    if auto_export:
        if args.category:
            # create a label from the category path (replace / with _)
            parsed = urlparse(args.category)
            cat_path = parsed.path.strip("/") or parsed.netloc
            label = sanitize_label(cat_path.replace("/", "_"))
            export_dir = export_base / label
            export_dir.mkdir(parents=True, exist_ok=True)
            # default output file under exports/<label>/<label>.jsonl or .csv
            if out_path is None:
                out_path = str(export_dir / f"{label}.{args.format}")
            # default images dir
            if images_dir is None and download_images:
                images_dir = str(export_dir / "images")
        elif args.url:
            # derive a label from the URL path last segment
            parsed = urlparse(args.url)
            parts = [p for p in parsed.path.split("/") if p]
            slug = parts[-1] if parts else parsed.netloc
            label = sanitize_label(slug)
            export_dir = export_base / label
            export_dir.mkdir(parents=True, exist_ok=True)
            if out_path is None:
                out_path = str(export_dir / f"{label}.{args.format}")
            if images_dir is None and download_images:
                images_dir = str(export_dir / "images")
        elif args.input:
            # use input filename as label
            inp = Path(args.input)
            label = sanitize_label(inp.stem)
            export_dir = export_base / label
            export_dir.mkdir(parents=True, exist_ok=True)
            if out_path is None:
                out_path = str(export_dir / f"{label}.{args.format}")
            if images_dir is None and download_images:
                images_dir = str(export_dir / "images")

    # call the processor with computed defaults
    process_urls(
        urls,
        out_path=(None if out_path == "-" else out_path),
        out_format=args.format,
        delay=args.delay,
        images_dir=images_dir,
        thumb_size=args.thumb_size,
    )

    # after processing, optionally auto-generate printable HTML (from JSONL)
    try:
        export_dir  # ensure variable exists when auto_export used
    except NameError:
        export_dir = None

    if auto_export and auto_html and out_path and args.format == "jsonl":
        try:
            # import the printable generator functions
            from tools.generate_printable import load_jsonl, render_html, normalize_local_image_paths
            jpath = Path(out_path)
            if jpath.exists():
                records = load_jsonl(jpath)
                # make local image paths relative to the printable.html location
                if export_dir is not None:
                    ph = export_dir / "printable.html"
                else:
                    ph = jpath.parent / "printable.html"
                try:
                    normalize_local_image_paths(records, ph)
                except Exception:
                    # fallback: continue without normalizing
                    pass
                html_content = render_html(records, title=label if 'label' in locals() else 'products', per_page=6, lang=args.html_lang, format_type=args.html_format)
                ph.write_text(html_content, encoding="utf-8")
                print("Wrote printable HTML:", ph)
        except Exception as exc:
            print("Failed to auto-generate printable HTML:", exc)


if __name__ == "__main__":
    main()
