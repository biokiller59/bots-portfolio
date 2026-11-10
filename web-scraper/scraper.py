"""Scrapes a product catalogue into Excel or CSV.

Demo target: books.toscrape.com (a public sandbox made for scraping practice).
Run:  python scraper.py --pages 3 --out books.xlsx
"""
import argparse
import csv
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
COLUMNS = ["title", "price_gbp", "rating", "in_stock", "url"]
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse(html, page_url):
    """Returns (rows, next_page_url or None)."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        rating_class = card.select_one("p.star-rating")["class"][-1]
        rows.append({
            "title": link["title"],
            "price_gbp": float(card.select_one(".price_color").text.strip().lstrip("£Â")),
            "rating": RATINGS.get(rating_class),
            "in_stock": "In stock" in card.select_one(".availability").text,
            "url": urljoin(page_url, link["href"]),
        })
    next_link = soup.select_one("li.next a")
    return rows, urljoin(page_url, next_link["href"]) if next_link else None


def scrape(start_url, max_pages, delay=0.5):
    rows, url = [], start_url
    session = requests.Session()
    session.headers["User-Agent"] = "catalogue-scraper-demo"
    for _ in range(max_pages):
        if not url:
            break
        response = session.get(url, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"
        page_rows, url = parse(response.text, response.url)
        rows += page_rows
        print(f"{response.url}: {len(page_rows)} items")
        time.sleep(delay)  # be polite to the site
    return rows


def save(rows, path):
    if path.endswith(".csv"):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    else:
        book = Workbook()
        sheet = book.active
        sheet.append(COLUMNS)
        for row in rows:
            sheet.append([row[c] for c in COLUMNS])
        book.save(path)


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--pages", type=int, default=3)
    args.add_argument("--out", default="books.xlsx", help=".xlsx or .csv")
    args = args.parse_args()
    data = scrape(START_URL, args.pages)
    save(data, args.out)
    print(f"Saved {len(data)} rows to {args.out}")
