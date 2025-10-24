#!/usr/bin/env python3
"""Simple product page scraper.

Extracts: product name, image url, price (local currency), origin, product code.
"""
import argparse
from typing import Optional, Dict

import requests
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except Exception:
    BeautifulSoup = None
    BS4_AVAILABLE = False


def load_html_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_html_from_url(url: str) -> str:
    # Try to use Playwright to render the page if available (some product badges are injected via JS).
    try:
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set user agent to avoid bot detection
                page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                })
                
                page.goto(url, timeout=30000)
                
                # Handle cookie consent dialogs
                try:
                    # Wait a moment for dialogs to appear
                    page.wait_for_timeout(2000)
                    
                    # Try various cookie consent buttons
                    consent_selectors = [
                        'button:has-text("Съгласие")',
                        'button:has-text("Разреши всички")', 
                        'button:has-text("Accept")',
                        'button:has-text("Приемам")',
                        'button[id*="accept"]',
                        'button[class*="accept"]',
                        '[data-testid*="accept"]'
                    ]
                    
                    for selector in consent_selectors:
                        try:
                            if page.locator(selector).count() > 0:
                                page.click(selector, timeout=2000)
                                page.wait_for_timeout(1000)
                                break
                        except Exception:
                            continue
                            
                except Exception:
                    pass
                
                # wait briefly for possible dynamic content after consent
                try:
                    page.wait_for_load_state('networkidle', timeout=8000)
                except Exception:
                    page.wait_for_timeout(3000)
                
                content = page.content()
                
                try:
                    page.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                return content
        except Exception:
            # if Playwright fails, fall back to requests
            pass
    except Exception:
        # Playwright not installed in this environment -> fallback
        pass

    # Fallback to requests with better headers
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or 'utf-8'
    return resp.text


def extract_product_info(html: str) -> Dict[str, Optional[str]]:
    title = None
    img = None
    price = None
    code = None
    price_currency_jsonld = None
    price_source = None
    # quantity-related fields (initialize early so JSON-LD parsing can reference)
    quantity_amount = None
    quantity_unit = None
    quantity_raw = None
    quantity_total_amount = None
    quantity_total_unit = None
    quantity_range = None

    # helper to normalize unit names (make available early for JSON-LD parsing)
    def normalize_unit(u: str) -> str:
        if not u:
            return u
        u = u.strip().lower()
        if u in ('ml', 'мил', 'мл', 'миллилитър', 'milliliter', 'millilitre'):
            return 'ml'
        if u in ('l', 'л', 'литър', 'liter', 'litre'):
            return 'l'
        if u in ('g', 'гр', 'г', 'грам', 'gram'):
            return 'g'
        if u in ('kg', 'кг', 'килограм', 'kilogram'):
            return 'kg'
        if u in ('бр', 'бр.', 'брой', 'pcs', 'pack', 'парче', 'парчета'):
            return 'pcs'
        return u

    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        # Prefer JSON-LD Product schema when available (more reliable)
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json as _json
                    data = _json.loads(script.string or "{}")
                except Exception:
                    continue
                # data can be a list or dict
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if isinstance(it, dict) and it.get("@type") and "Product" in it.get("@type"):
                        # name
                        title = title or it.get("name")
                        # image may be list or string
                        img_val = it.get("image")
                        if img_val:
                            if isinstance(img_val, list):
                                img = img or img_val[0]
                            else:
                                img = img or img_val
                        # sku/code
                        code = code or it.get("sku") or it.get("productID")
                        # Try to extract quantity from structured fields if available
                        try:
                            # weight can be a dict with value and unit or a string like '500 g'
                            if not quantity_amount:
                                w = it.get('weight') or it.get('size') or it.get('weightSpecification')
                                if isinstance(w, dict):
                                    val = w.get('value') or w.get('amount') or w.get('measurement')
                                    unit = w.get('unitText') or w.get('unit')
                                    if val and unit:
                                        try:
                                            quantity_amount = str(float(val)) if isinstance(val, (int, float)) else str(val)
                                        except Exception:
                                            quantity_amount = str(val)
                                        quantity_unit = normalize_unit(unit)
                                        quantity_raw = f"{quantity_amount} {quantity_unit}"
                                elif isinstance(w, str):
                                    import re as _re
                                    m = _re.search(r'(\d+[\d,.]*)\s*(ml|мл|l|л|kg|кг|g|гр|г)\b', w, _re.I)
                                    if m:
                                        quantity_amount = m.group(1).replace(',', '.')
                                        quantity_unit = normalize_unit(m.group(2))
                                        quantity_raw = m.group(0)
                                # additionalProperty sometimes carries size/weight
                                if not quantity_amount and isinstance(it.get('additionalProperty'), (list, dict)):
                                    props = it.get('additionalProperty') if isinstance(it.get('additionalProperty'), list) else [it.get('additionalProperty')]
                                    for prop in props:
                                        if isinstance(prop, dict):
                                            pv = prop.get('value') or prop.get('valueReference')
                                            if isinstance(pv, str):
                                                import re as _re
                                                m = _re.search(r'(\d+[\d,.]*)\s*(ml|мл|l|л|kg|кг|g|гр|г)\b', pv, _re.I)
                                                if m:
                                                    quantity_amount = m.group(1).replace(',', '.')
                                                    quantity_unit = normalize_unit(m.group(2))
                                                    quantity_raw = m.group(0)
                                                    break
                        except Exception:
                            pass
                        # offers may contain price
                        offers = it.get("offers")
                        if offers:
                            # capture price and priceCurrency when present in JSON-LD
                            if isinstance(offers, dict):
                                if offers.get("price"):
                                    price = price or offers.get("price")
                                    price_source = 'jsonld'
                                # prefer priceCurrency from JSON-LD over parsing text
                                if offers.get("priceCurrency"):
                                    price_currency_jsonld = offers.get("priceCurrency")
                                else:
                                    price_currency_jsonld = None
                            elif isinstance(offers, list) and offers:
                                first = offers[0]
                                if first.get("price"):
                                    price = price or first.get("price")
                                    price_source = 'jsonld'
                                price_currency_jsonld = first.get("priceCurrency") if first.get("priceCurrency") else None
                        else:
                            price_currency_jsonld = None
                        # try common origin fields in JSON-LD (countryOfOrigin, country, manufacturer/addressCountry)
                            # origin not collected (removed)
                        # we found product info, break
                        if title or img or price or code:
                            break
                if title or img or price or code:
                    break
        except Exception:
            # keep going with HTML-based heuristics
            pass
        sel_title = soup.select_one("h1.product-title, .product-title, h1")
        if sel_title:
            title = sel_title.get_text(strip=True)

        # Clean noisy title prefixes frequently present on the site
        def clean_title(t: str) -> str:
            if not t:
                return t
            t = t.strip()
            import re as _re
            # remove common site-added prefixes and availability notices
            t = _re.sub(r'^(\s*Български продукт[:\-\s]*)', '', t, flags=_re.I)
            t = _re.sub(r'^(\s*Продуктът не е наличен[:\-\s]*)', '', t, flags=_re.I)
            # remove trailing site markers like ' - eBag' or '| eBag'
            t = _re.sub(r'\s+[\-\|]\s+eBag$', '', t, flags=_re.I)
            return t.strip()

        if title:
            title = clean_title(title)

        if not img:
            sel_img = soup.select_one(".product-image img, .product img, img[alt]")
            if sel_img and sel_img.has_attr("src"):
                img = sel_img["src"]

        # Try to extract a clean price string from visible HTML if JSON-LD didn't provide one
        def find_price_in_text(txt: str):
            import re as _re
            # match numbers with currency tokens like '3.84 лв.' or '1,97 €' or ISO codes
            m = _re.search(r"(\d+[\d.,]*\s*(?:лв\.?|BGN|€|EUR))", txt, _re.I)
            if m:
                return m.group(0).strip()
            return None

        if not price:
            sel_price = soup.select_one(".price, .product-price, .price-block .price, .product-prices")
            if sel_price:
                text = sel_price.get_text(" ", strip=True)
                ptxt = find_price_in_text(text)
                if ptxt:
                    price = ptxt
                    price_source = 'html'
            if not price:
                # fallback to scanning page text for a price-like token
                page_text = soup.get_text(" ", strip=True)
                ptxt = find_price_in_text(page_text)
                if ptxt:
                    price = ptxt
                    price_source = 'html'

        # Look for visible label "Код" and try to extract the nearby code value.
        # Prefer not to overwrite an existing code (for example from JSON-LD).
        for el in soup.find_all(string=True):
            if code:
                break
            txt = el.strip()
            if not txt:
                continue
            if "код" in txt.lower():
                parent = el.parent
                # prefer an explicit <strong> sibling/value if present
                strong = parent.find("strong")
                if strong and strong.get_text(strip=True):
                    code = strong.get_text(strip=True)
                    break
                # try immediate next sibling elements for a code-like token
                import re as _re
                found_code = None
                sib = parent.next_sibling
                # walk a few siblings to find a digit/alnum token
                steps = 0
                while sib is not None and steps < 6 and not found_code:
                    try:
                        stext = sib.get_text(" ", strip=True) if hasattr(sib, 'get_text') else str(sib).strip()
                    except Exception:
                        stext = str(sib).strip()
                    if stext:
                        m = _re.search(r'([A-Za-z0-9\-_/]+)', stext)
                        if m:
                            found_code = m.group(1)
                            break
                    sib = sib.next_sibling
                    steps += 1

                # if not found in siblings, search the following text nodes on the page
                if not found_code:
                    nxt = parent.find_next(string=_re.compile(r'[A-Za-z0-9\-_/]{3,}'))
                    if nxt:
                        m = _re.search(r'([A-Za-z0-9\-_/]+)', nxt.strip())
                        if m:
                            found_code = m.group(1)

                # fallback: clean parent text by removing the label
                if found_code:
                    code = found_code.strip()
                else:
                    code = parent.get_text(separator=" ", strip=True).replace("Код", "").replace("код", "").strip()
        # additional code/SKU heuristics: data attributes, ids, classes
        if not code:
            # look for attributes like data-sku, data-article
            for el in soup.find_all(attrs=True):
                for aname, aval in el.attrs.items():
                    if aname.lower() in ('data-sku', 'data-sku-id', 'data-article', 'data-product-sku') and aval:
                        code = str(aval).strip()
                        break
                if code:
                    break
        if not code:
            # search elements with id/class indicating sku/code
            for el in soup.find_all(True):
                aid = (el.get('id') or '').lower()
                cls = ' '.join(el.get('class') or []).lower()
                if any(k in aid for k in ('sku', 'code', 'артикул')) or any(k in cls for k in ('sku', 'code', 'артикул')):
                    txt = el.get_text(' ', strip=True)
                    if txt:
                        # extract probable code token
                        import re as _re
                        m = _re.search(r'([A-Za-z0-9\-_/]+)', txt)
                        if m:
                            code = m.group(1)
                            break
        # origin removed - no further heuristics
    else:
        # Fallback naive parsing using regex for environments without BeautifulSoup.
        import re

        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

        m = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", html, re.I)
        if m:
            img = m.group(1)

        m = re.search(r"class=[\"']price[\"'][^>]*>([^<]+)<", html, re.I)
        if m:
            price = m.group(1).strip()
        else:
            m = re.search(r"(\d+[\d,.]*\s*(?:лв\.|€))", html)
            if m:
                price = m.group(1).strip()

        m = re.search(r"Произход[\s\S]*?<strong>([^<]+)</strong>", html, re.I)
        if m:
            origin = m.group(1).strip()
        m = re.search(r"Код[\s\S]*?<strong>([^<]+)</strong>", html, re.I)
        if m:
            code = m.group(1).strip()

    # Post-process price to split amount and localized Bulgarian currency label
    price_amount = None
    price_currency_bg = None
    # quantity extraction
    quantity_amount = None
    quantity_unit = None
    if price:
        import re

        # common tokens and their Bulgarian labels
        token_map = {
            "лв.": "лв.",
            "лв": "лв.",
            "BGN": "лв.",
            "€": "евро",
            "EUR": "евро",
            "eur": "евро",
        }

        # find currency token in the price string
        tok = None
        for t in token_map:
            if t in price:
                tok = t
                break

        # extract numeric amount (first occurrence of a number-like token)
        m = re.search(r"(\d+[\d,.]*)", price)
        if m:
            price_amount = m.group(1).replace(',', '.').strip()
        if tok:
            price_currency_bg = token_map.get(tok)
        else:
            # fallback to JSON-LD priceCurrency if present
            pc = None
            try:
                pc = price_currency_jsonld  # set when parsing JSON-LD offers above
            except Exception:
                pc = None
            if pc:
                # map known ISO codes
                if pc.upper() == 'BGN':
                    price_currency_bg = 'лв.'
                elif pc.upper() in ('EUR', 'EUR '):
                    price_currency_bg = 'евро'

    # Quantity extraction: look for structured JSON-LD fields first (weight, size, etc.)
    quantity_raw = None
    quantity_total_amount = None
    quantity_total_unit = None
    quantity_range = None
    try:
        # search for patterns like '500 ml', '1.5 L', '250 g', '1 kg', Bulgarian variants 'мл', 'л', 'г', 'кг'
        import re

        # try JSON-LD: look for weight/size/measurement fields in Product JSON-LD already parsed above
        # Enhanced approach: prioritize JSON-LD description field and look for quantity patterns there
        if BS4_AVAILABLE and BeautifulSoup is not None:
            text_sources = []
            
            # PRIORITY 1: JSON-LD Product description (where most quantities are found)
            for script in soup.find_all('script', type='application/ld+json'):
                if not script.string:
                    continue
                try:
                    import json
                    data = json.loads(script.string)
                    if data.get('@type') == 'Product' and data.get('description'):
                        # Add product description with high priority
                        text_sources.append(data.get('description'))
                        break
                except:
                    continue
                    
            # PRIORITY 2: Include all JSON-LD scripts that might contain quantity info
            for script in soup.find_all('script', type='application/ld+json'):
                if not script.string:
                    continue
                stext = script.string.lower()
                if any(k in stext for k in ('weight', 'size', 'additionalproperty', 'measurement', 'kg', 'g', 'ml', 'l', 'volume', 'опаковка', 'package')):
                    text_sources.append(script.string)
                    
            # PRIORITY 3: Meta description and product info sections
            meta = soup.find('meta', attrs={'name': 'description'})
            if meta and meta.get('content'):
                text_sources.append(meta.get('content'))
            for sel in ('.product-description', '.description', '#description', '.prod-desc', '.product-info', '.product-title', 'h1'):
                el = soup.select_one(sel)
                if el:
                    text_sources.append(el.get_text(' ', strip=True))
                    
            # PRIORITY 4: Look for quantity patterns in structured page elements
            # Check elements that might contain product specifications
            for sel in soup.find_all(['div', 'span', 'p', 'td'], class_=re.compile(r'product|item|spec|detail|info', re.I)):
                if sel:
                    sel_text = sel.get_text(' ', strip=True)
                    # Only include if it contains quantity indicators
                    if re.search(r'\d+[\d,.]*\s*(?:г|гр|грам|кг|килограм|мл|милилитър|л|литър|ml|l|kg|g)', sel_text, re.I):
                        text_sources.append(sel_text)
                        
            # PRIORITY 5: Full page text as fallback (limited to first part to avoid noise)
            page_text = soup.get_text(' ', strip=True)
            text_sources.append(page_text[:5000])  # Extended to 5000 chars for better coverage
        else:
            text_sources = [html]

        found = False
        # unit token (include pcs/бр and allow no-space variants and NBSP)
        # expanded to include full Bulgarian words
        unit_tokens = r'(?:ml|мл|милилитър|milliliter|millilitre|l|л|литър|liter|litre|kg|кг|килограм|kilogram|g|гр|г|грам|gram|бр|бр\.|брой|pcs|pack|пакет|парче|парчета)'
        nbsp = r'[\s\u00A0]'
        
        # Enhanced patterns to capture Bulgarian packaging info
        # Pattern for "Опаковка 125 г" or "Package 125 g" 
        package_pattern = re.compile(r'(?:Опаковка|Package|Пакет|Опак\.?)' + nbsp + r'*(?P<amt>\d+[\d,.]*)' + nbsp + r'*(?P<unit>' + unit_tokens + r')\b', re.I)
        # multiplier pattern first, e.g. '5 x 200 g' (add word boundary to avoid matching currency parts)
        mult_pattern = re.compile(r'(?P<count>\d+)' + nbsp + r'*(?:бр\.?|pcs|pack)?' + nbsp + r'*[x×хX]' + nbsp + r'*(?P<amt>\d+[\d,.]*)' + nbsp + r'*(?P<unit>' + unit_tokens + r')\b', re.I)
        # range pattern like '67-90 g'
        range_pattern = re.compile(r'(?P<min>\d+[\d,.]*)\s*[-–—]\s*(?P<max>\d+[\d,.]*)' + nbsp + r'*(?P<unit>' + unit_tokens + r')\b', re.I)
        # single quantity like '330 мл' or '500гр' (no space)
        qty_pattern = re.compile(r'(?P<amt>\d+[\d,.]*)' + nbsp + r'*(?P<unit>' + unit_tokens + r')\b', re.I)

        for src in text_sources:
            if not src:
                continue
                
            # try package pattern first (highest priority) - "Опаковка 125 г"
            m = package_pattern.search(src)
            if m:
                quantity_raw = m.group(0).strip()
                amt = m.group('amt').replace(',', '.').strip()
                unit_raw = m.group('unit')
                unit = normalize_unit(unit_raw)
                quantity_amount = amt
                quantity_unit = unit
                found = True
                break
                
            # try multiplier pattern to capture raw like '5 x 200 g'
            m = mult_pattern.search(src)
            if m:
                quantity_raw = m.group(0).strip()
                # keep existing normalized amount/unit behavior: set quantity_amount to per-piece amt
                amt = m.group('amt').replace(',', '.').strip()
                unit_raw = m.group('unit')
                unit = normalize_unit(unit_raw)
                quantity_amount = amt
                quantity_unit = unit
                # compute total amount if count available
                try:
                    cnt = int(m.group('count'))
                    # compute total in same unit (per-piece * count)
                    try:
                        total = float(amt) * cnt
                        # format as string without unnecessary decimals
                        quantity_total_amount = (int(total) if total.is_integer() else round(total, 3))
                        quantity_total_unit = unit
                    except Exception:
                        quantity_total_amount = None
                        quantity_total_unit = None
                except Exception:
                    quantity_total_amount = None
                    quantity_total_unit = None
                found = True
                break
            # try range pattern (e.g., '67-90 g')
            m = range_pattern.search(src)
            if m:
                quantity_raw = m.group(0).strip()
                mn = m.group('min').replace(',', '.').strip()
                mx = m.group('max').replace(',', '.').strip()
                unit_raw = m.group('unit')
                unit = normalize_unit(unit_raw)
                # store range as numeric min/max
                try:
                    quantity_range = {'min': float(mn), 'max': float(mx), 'unit': unit}
                    # by default, choose the max as quantity_amount for conservative estimation
                    quantity_amount = mx
                    quantity_unit = unit
                except Exception:
                    quantity_range = None
                found = True
                break
            m = qty_pattern.search(src)
            if m:
                quantity_raw = m.group(0).strip()
                amt = m.group('amt').replace(',', '.').strip()
                unit_raw = m.group('unit')
                unit = normalize_unit(unit_raw)
                
                # Skip if this looks like a price (common false positives)
                # Skip amounts that are too large to be reasonable quantities for common units
                try:
                    amt_float = float(amt)
                    # Skip prices (usually much higher numbers with specific units)
                    if unit in ['л', 'l'] and amt_float > 10:  # More than 10L is likely a price
                        continue
                    if unit in ['г', 'g'] and amt_float > 5000:  # More than 5kg as grams is likely wrong
                        continue
                    # Skip very small quantities that are likely measurement errors
                    if unit in ['кг', 'kg'] and amt_float < 0.01:
                        continue
                except:
                    pass
                
                # handle piece/unit tokens like 'бр' or 'pcs' -> standardize to 'pcs'
                if unit in ('бр', 'бр.', 'pcs', 'pack', 'парче', 'парчета'):
                    # treat as count if no multiplier present
                    quantity_amount = amt
                    quantity_unit = 'pcs'
                else:
                    quantity_amount = amt
                    quantity_unit = unit
                found = True
                break

        # If not found yet, look for label:value patterns that often appear in product specs
        if not found:
            try:
                label_re = re.compile(r'(Тегло|Обем|Нетно тегло|В опаковка|Опаковка|Количество|Съдържание|Размер|Size|Weight|Volume)[:\s]*([^<\n]{1,120})', re.I)
                for src in text_sources:
                    if not src:
                        continue
                    lm = label_re.search(src)
                    if lm:
                        candidate = lm.group(2)
                        mm = qty_pattern.search(candidate)
                        if mm:
                            quantity_raw = mm.group(0).strip()
                            amt = mm.group('amt').replace(',', '.').strip()
                            unit_raw = mm.group('unit')
                            unit = normalize_unit(unit_raw)
                            if unit in ('бр', 'бр.', 'pcs', 'pack', 'парче', 'парчета'):
                                quantity_amount = amt
                                quantity_unit = 'pcs'
                            else:
                                quantity_amount = amt
                                quantity_unit = unit
                            found = True
                            break
                    # also try table rows like '<th>Тегло</th><td>500 г</td>' by searching raw HTML
                    if '<th' in src or '<td' in src:
                        m2 = re.search(r'<th[^>]*>\s*(?:Тегло|Опаковка|Количество)\s*</th>\s*<td[^>]*>([^<]{1,120})</td>', src, re.I)
                        if m2:
                            candidate = m2.group(1)
                            mm = qty_pattern.search(candidate)
                            if mm:
                                quantity_raw = mm.group(0).strip()
                                amt = mm.group('amt').replace(',', '.').strip()
                                unit_raw = mm.group('unit')
                                unit = normalize_unit(unit_raw)
                                if unit in ('бр', 'бр.', 'pcs', 'pack', 'парче', 'парчета'):
                                    quantity_amount = amt
                                    quantity_unit = 'pcs'
                                else:
                                    quantity_amount = amt
                                    quantity_unit = unit
                                found = True
                                break
            except Exception:
                pass
    except Exception:
        # keep quantity as None on error
        quantity_amount = None
        quantity_unit = None

    # origin not returned per request

    return {
        "name": title,
        "image": img,
        "price": price,
        "price_amount": price_amount,
        "price_currency_bg": price_currency_bg,
        "price_source": price_source,
        # origin omitted intentionally
        "code": code,
        "quantity_raw": quantity_raw,
        "quantity_amount": quantity_amount,
        "quantity_unit": quantity_unit,
        "quantity_total_amount": quantity_total_amount,
        "quantity_total_unit": quantity_total_unit,
        "quantity_range": quantity_range,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scrape a product page and extract info")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL of product page to scrape")
    group.add_argument("--file", help="Local HTML file to parse")
    args = parser.parse_args(argv)

    html = None
    if args.url:
        html = load_html_from_url(args.url)
    else:
        html = load_html_from_file(args.file)

    info = extract_product_info(html)
    for k, v in info.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
