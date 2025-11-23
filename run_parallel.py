import os
import re
import sys
import requests
import collections
from concurrent.futures import ThreadPoolExecutor, as_completed
from browserstack_scraper import run_test, NUM_ARTICLES, IMAGE_FOLDER

os.makedirs(IMAGE_FOLDER, exist_ok=True)

# -------------------------------------------------------------------
# BrowserStack Capability Matrix (5 parallel runs)
# -------------------------------------------------------------------
capabilities_list = [
    {
        "browserName": "chrome",
        "browserVersion": "latest",
        "bstack:options": {"os": "Windows", "osVersion": "11", "sessionName": "Chrome Test"}
    },
    {
        "browserName": "firefox",
        "browserVersion": "latest",
        "bstack:options": {"os": "Windows", "osVersion": "11", "sessionName": "Firefox Test"}
    },
    {
        "browserName": "edge",
        "browserVersion": "latest",
        "bstack:options": {"os": "Windows", "osVersion": "11", "sessionName": "Edge Test"}
    },
    {
        "browserName": "chrome",
        "bstack:options": {
            "deviceName": "Samsung Galaxy S22",
            "osVersion": "12",
            "realMobile": "true",
            "sessionName": "Android Chrome Test"
        }
    },
    {
        "browserName": "chrome",
        "bstack:options": {
            "deviceName": "iPhone 14",
            "osVersion": "16",
            "platformName": "iOS",
            "realMobile": "true",
            "sessionName": "iPhone 14 Chrome Test"
        }
    }
]

# -------------------------------------------------------------------
# Helper for saving article images
# -------------------------------------------------------------------
def download_image(url, folder, prefix, index):
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        ext = "jpg"
        if "png" in ctype: ext = "png"
        if "webp" in ctype: ext = "webp"
        fname = f"{prefix}_{index}.{ext}"
        path = os.path.join(folder, fname)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except:
        return ""


# -------------------------------------------------------------------
# Main Orchestration
# -------------------------------------------------------------------
def main():
    results = []

    # Run sessions in parallel
    with ThreadPoolExecutor(max_workers=5) as exec:
        futures = {exec.submit(run_test, caps): caps for caps in capabilities_list}
        for f in as_completed(futures):
            res = f.result()
            caps = futures[f]
            res["sessionName"] = caps["bstack:options"]["sessionName"]
            results.append(res)

    # Merge articles
    all_articles = []
    for r in results:
        all_articles.extend(r.get("items", []))

    # Deduplicate by URL
    seen = set()
    articles = []
    for a in all_articles:
        url = a.get("url")
        if url and url not in seen:
            seen.add(url)
            articles.append(a)
        if len(articles) == NUM_ARTICLES:
            break

    # Download images
    for idx, art in enumerate(articles, 1):
        saved = download_image(art.get("image_url"), IMAGE_FOLDER, "article", idx)
        art["image_path"] = saved

    # Print Spanish content
    print("\n=== SPANISH TITLES & CONTENT ===\n")
    for art in articles:
        print("URL:", art.get("url"))
        print("TITLE (ES):", art.get("title_es"))
        print("CONTENT (ES):", (art.get("content_es") or "")[:800])
        print("-" * 80)

    # English translations
    headers_en = [a["title_en"] for a in articles if a.get("title_en")]
    print("\n=== ENGLISH TRANSLATED TITLES ===\n")
    for h in headers_en:
        print(h)

    # Word frequency
    words = []
    for h in headers_en:
        cleaned = re.sub(r"[^\w\s']", " ", h).lower()
        words.extend(cleaned.split())

    freq = collections.Counter(words)
    repeated = {w: c for w, c in freq.items() if c >= 2}

    print("\n=== WORDS REPEATED >= 2 TIMES ===\n")
    for w, c in repeated.items():
        print(f"{w}: {c}")

    # -------------------------------------------------------------------
    # Final Summary Block
    # -------------------------------------------------------------------
    print("\n==============================")
    print(" BROWSERSTACK TEST SUMMARY")
    print("==============================")
    for r in results:
        name = r["sessionName"]
        if r["success"]:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} - {r.get('error')}")
    print("==============================\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
