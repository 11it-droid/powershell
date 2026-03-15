"""
Daraz Shop Scraper — auto-installs dependencies, then scrapes.
Run: python shop_scraper.py
"""

import subprocess, sys

def _install(pkg):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

try:
    import aiohttp
except ImportError:
    print('Installing aiohttp...'); _install('aiohttp'); import aiohttp

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print('Installing openpyxl...'); _install('openpyxl')
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

import asyncio
import json
import logging
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SHOPS = [
    "tvhutandelectronics",
    "shaman-international",
]

OUTPUT_FILE = f"daraz_shops_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
MAX_PAGES = 50
MIN_DELAY = 1.5
MAX_DELAY = 3.5

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.daraz.com.bd/",
}

HEADER_FILL  = PatternFill("solid", start_color="1F3864")
SUBHEAD_FILL = PatternFill("solid", start_color="2E75B6")
ALT_FILL     = PatternFill("solid", start_color="EBF3FB")
WHITE_FILL   = PatternFill("solid", start_color="FFFFFF")
ACCENT_FILL  = PatternFill("solid", start_color="D6E4F0")
HEADER_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=11)
TITLE_FONT   = Font(name="Arial", bold=True, color="1F3864", size=14)
BOLD_FONT    = Font(name="Arial", bold=True, size=10)
NORMAL_FONT  = Font(name="Arial", size=10)
LINK_FONT    = Font(name="Arial", size=10, color="0563C1", underline="single")
THIN_BORDER  = Border(
    left=Side(style="thin", color="BDD7EE"), right=Side(style="thin", color="BDD7EE"),
    top=Side(style="thin", color="BDD7EE"), bottom=Side(style="thin", color="BDD7EE"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
RIGHT  = Alignment(horizontal="right",  vertical="center")


def build_ajax_url(shop_slug, page):
    is_first = "true" if page == 1 else "false"
    return (f"https://www.daraz.com.bd/{shop_slug}/"
            f"?ajax=true&from=wangpu&isFirstRequest={is_first}"
            f"&langFlag=en&page={page}&pageTypeId=2&q=All-Products&sort=order")


def parse_sold(s):
    if not s: return None
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def parse_products(data, shop_slug):
    try: items = data["mods"]["listItems"]
    except (KeyError, TypeError): return []
    products = []
    for item in items:
        if item.get("tItemType") != "nt_product": continue
        if not item.get("itemSoldCntShow"): continue
        url = item.get("itemUrl", "")
        if url.startswith("//"): url = "https:" + url
        products.append({
            "shop":           shop_slug,
            "item_id":        item.get("itemId") or item.get("nid"),
            "name":           item.get("name", ""),
            "brand":          item.get("brandName", "") or "N/A",
            "seller":         item.get("sellerName", ""),
            "price":          int(item["price"]) if item.get("price") else None,
            "original_price": int(item["originalPrice"]) if item.get("originalPrice") else None,
            "discount":       item.get("discount", ""),
            "rating":         float(item["ratingScore"]) if item.get("ratingScore") else None,
            "reviews":        int(item["review"]) if item.get("review") else None,
            "sold_per_month": parse_sold(item.get("itemSoldCntShow")),
            "in_stock":       item.get("inStock", False),
            "location":       item.get("location", ""),
            "sku_id":         item.get("skuId"),
            "image":          item.get("image", ""),
            "url":            url,
            "scraped_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return products


async def fetch_page(session, shop_slug, page):
    try:
        async with session.get(build_ajax_url(shop_slug, page), headers=HTTP_HEADERS,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logging.warning(f"[{shop_slug}] page {page} HTTP {resp.status}")
                return None
            return json.loads(await resp.text())
    except Exception as e:
        logging.error(f"[{shop_slug}] page {page} error: {e}")
        return None


async def scrape_shop(session, shop_slug):
    all_products = []
    logging.info(f"Scraping: {shop_slug}")
    for page in range(1, MAX_PAGES + 1):
        data = await fetch_page(session, shop_slug, page)
        if data is None: break
        raw = data.get("mods", {}).get("listItems", [])
        if not raw:
            logging.info(f"  [{shop_slug}] page {page} empty, done.")
            break
        products = parse_products(data, shop_slug)
        all_products.extend(products)
        logging.info(f"  [{shop_slug}] page {page} → {len(products)}/{len(raw)} with Sold/Month")
        if len(products) == 0: break
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    return all_products


async def scrape_all():
    all_products = []
    async with aiohttp.ClientSession() as session:
        for shop in SHOPS:
            products = await scrape_shop(session, shop)
            all_products.extend(products)
            logging.info(f"  ✓ {shop}: {len(products)} products")
    return all_products


def write_summary_sheet(ws, products):
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:H1")
    ws["A1"] = "Daraz Shop Scraper — Summary Report"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = CENTER
    ws["A1"].fill = ACCENT_FILL
    ws.row_dimensions[1].height = 30

    ws.merge_cells("A2:H2")
    ws["A2"] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   |   Shops: {len(SHOPS)}   |   Total Products: {len(products)}"
    ws["A2"].font = Font(name="Arial", italic=True, size=10, color="555555")
    ws["A2"].alignment = CENTER
    ws.row_dimensions[2].height = 18

    by_shop = defaultdict(list)
    for p in products:
        by_shop[p["shop"]].append(p)

    row = 4
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1, value="Per-Shop Overview").font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    ws.cell(row=row, column=1).fill = SUBHEAD_FILL
    ws.cell(row=row, column=1).alignment = CENTER
    ws.row_dimensions[row].height = 22
    row += 1

    for col, h in enumerate(["Shop","Products","Total Sold/Mo","Avg Price (৳)","Avg Discount","Avg Rating","Top Brand","Top Product (by Sold)"], 1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill = HEADER_FILL; c.font = HEADER_FONT; c.alignment = CENTER; c.border = THIN_BORDER
    ws.row_dimensions[row].height = 20
    row += 1

    for i, (shop, prods) in enumerate(by_shop.items()):
        fill = ALT_FILL if i % 2 == 0 else WHITE_FILL
        sold_vals  = [p["sold_per_month"] for p in prods if p["sold_per_month"]]
        price_vals = [p["price"] for p in prods if p["price"]]
        rating_vals= [p["rating"] for p in prods if p["rating"]]
        disc_vals  = []
        for p in prods:
            d = p.get("discount","")
            if d and d not in ("","0%"):
                try: disc_vals.append(int(d.replace("%","").replace("-","").replace("+","")))
                except: pass
        brand_counts = defaultdict(int)
        for p in prods:
            if p["brand"] and p["brand"] != "N/A": brand_counts[p["brand"]] += 1
        top_brand = max(brand_counts, key=brand_counts.get) if brand_counts else "N/A"
        top_prod = max(prods, key=lambda x: x["sold_per_month"] or 0)
        vals = [
            shop, len(prods), sum(sold_vals),
            round(sum(price_vals)/len(price_vals)) if price_vals else 0,
            f"{round(sum(disc_vals)/len(disc_vals))}%" if disc_vals else "N/A",
            round(sum(rating_vals)/len(rating_vals),1) if rating_vals else "N/A",
            top_brand,
            top_prod["name"][:60] + ("…" if len(top_prod["name"])>60 else ""),
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.fill = fill; c.font = NORMAL_FONT; c.border = THIN_BORDER
            c.alignment = LEFT if col in (1,8) else CENTER
        ws.row_dimensions[row].height = 18
        row += 1

    row += 1
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1, value="Top 10 Products by Sold/Month (All Shops)").font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    ws.cell(row=row, column=1).fill = SUBHEAD_FILL
    ws.cell(row=row, column=1).alignment = CENTER
    ws.row_dimensions[row].height = 22
    row += 1

    for col, h in enumerate(["#","Shop","Name","Brand","Price (৳)","Discount","Rating","Sold/Month"], 1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill = HEADER_FILL; c.font = HEADER_FONT; c.alignment = CENTER; c.border = THIN_BORDER
    ws.row_dimensions[row].height = 20
    row += 1

    for i, p in enumerate(sorted(products, key=lambda x: x["sold_per_month"] or 0, reverse=True)[:10], 1):
        fill = ALT_FILL if i % 2 == 0 else WHITE_FILL
        for col, val in enumerate([i, p["shop"], p["name"][:60]+("…" if len(p["name"])>60 else ""),
                                    p["brand"], p["price"], p["discount"],
                                    p["rating"] or "N/A", p["sold_per_month"]], 1):
            c = ws.cell(row=row, column=col, value=val)
            c.fill = fill; c.font = NORMAL_FONT; c.border = THIN_BORDER
            c.alignment = LEFT if col in (3,4) else CENTER
        ws.row_dimensions[row].height = 18
        row += 1

    for col, w in enumerate([6,22,60,16,14,12,10,14], 1):
        ws.column_dimensions[get_column_letter(col)].width = w


def write_raw_sheet(ws, products):
    ws.title = "Raw Data"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

    columns = [
        ("Shop","shop",18), ("Item ID","item_id",14), ("Name","name",55),
        ("Brand","brand",14), ("Seller","seller",22), ("Price (৳)","price",12),
        ("Orig Price (৳)","original_price",14), ("Discount","discount",10),
        ("Rating","rating",10), ("Reviews","reviews",10), ("Sold/Month","sold_per_month",13),
        ("In Stock","in_stock",10), ("Location","location",12),
        ("SKU ID","sku_id",18), ("URL","url",40), ("Scraped At","scraped_at",20),
    ]

    for col, (label, _, width) in enumerate(columns, 1):
        c = ws.cell(row=1, column=col, value=label)
        c.fill = HEADER_FILL; c.font = HEADER_FONT; c.alignment = CENTER; c.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 22

    for row_idx, p in enumerate(products, 2):
        fill = ALT_FILL if row_idx % 2 == 0 else WHITE_FILL
        for col, (_, key, _) in enumerate(columns, 1):
            val = p.get(key)
            c = ws.cell(row=row_idx, column=col, value=val)
            c.fill = fill; c.border = THIN_BORDER
            if key == "url" and val:
                c.font = LINK_FONT; c.hyperlink = val; c.alignment = LEFT
            elif key == "in_stock":
                c.value = "Yes" if val else "No"
                c.font = Font(name="Arial", size=10, color="00703C" if val else "C00000", bold=True)
                c.alignment = CENTER
            elif key in ("price","original_price","sold_per_month","reviews"):
                c.font = NORMAL_FONT; c.alignment = RIGHT
            elif key == "rating":
                c.font = NORMAL_FONT; c.alignment = CENTER
            else:
                c.font = NORMAL_FONT; c.alignment = LEFT
        ws.row_dimensions[row_idx].height = 16


def save_excel(products, filepath):
    if not products:
        logging.warning("No products to save.")
        return
    wb = Workbook()
    write_summary_sheet(wb.active, products)
    write_raw_sheet(wb.create_sheet(), products)
    wb.save(filepath)
    logging.info(f"\n✓ Saved {len(products)} products → {filepath}")


def main():
    start = time.time()
    products = asyncio.run(scrape_all())
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_FILE)
    save_excel(products, output_path)
    logging.info(f"Done in {time.time()-start:.1f}s — {len(products)} products across {len(SHOPS)} shops")


if __name__ == "__main__":
    main()
