import os
import time
from typing import Dict, Any, List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

USERNAME = os.getenv("BROWSERSTACK_USERNAME")
ACCESS_KEY = os.getenv("BROWSERSTACK_ACCESS_KEY")

NUM_ARTICLES = 5
DEFAULT_WAIT = 12
IMAGE_FOLDER = "article_images"

translator = GoogleTranslator(source="es", target="en")

os.makedirs(IMAGE_FOLDER, exist_ok=True)


# -------------------------------------------------------------------
# WebDriver creation using Selenium 4 Options API
# -------------------------------------------------------------------
def build_driver(capabilities: Dict[str, Any]) -> webdriver.Remote:
    browser_name = capabilities["browserName"].lower()

    if browser_name == "chrome":
        options = ChromeOptions()
    elif browser_name == "firefox":
        options = FirefoxOptions()
    elif browser_name == "edge":
        options = EdgeOptions()
    else:
        options = ChromeOptions()

    # Normal capabilities
    for key, value in capabilities.items():
        if key != "bstack:options":
            options.set_capability(key, value)

    # Nested BrowserStack options
    options.set_capability("bstack:options", capabilities["bstack:options"])

    driver = webdriver.Remote(
        command_executor=f"https://{USERNAME}:{ACCESS_KEY}@hub.browserstack.com/wd/hub",
        options=options
    )
    return driver


# -------------------------------------------------------------------
# Fast cookie acceptance (no long waits)
# -------------------------------------------------------------------
def quick_accept_cookies(driver) -> bool:
    selectors = [
        (By.XPATH, "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]"),
        (By.XPATH, "//button[contains(., 'Aceptar')]"),
        (By.CSS_SELECTOR, "button[aria-label*='accept'], button[aria-label*='Aceptar']")
    ]

    for by, sel in selectors:
        try:
            for btn in driver.find_elements(by, sel):
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue

    # fallback scan
    try:
        for b in driver.find_elements(By.TAG_NAME, "button"):
            text = (b.text or b.get_attribute("aria-label") or "").lower()
            if "accept" in text or "acept" in text:
                driver.execute_script("arguments[0].click();", b)
                return True
    except Exception:
        pass

    return False


# -------------------------------------------------------------------
# NNavigate to Opinion section
# -------------------------------------------------------------------
def click_opinion(driver, wait):
    # Desktop attempt
    try:
        el = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 "//a[contains(translate(normalize-space(.),'ÁÉÍÓÚÜÑ','áéíóúüñ'),'opinión') "
                 "or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'opinion')]"
                 )
            ),
            DEFAULT_WAIT
        )
        driver.execute_script("arguments[0].click();", el)
        return
    except Exception:
        pass

    # Mobile: hamburger
    menu_selectors = [
        (By.XPATH, "//button[contains(@aria-label,'Menu') or contains(@aria-label,'Menú')]"),
        (By.CSS_SELECTOR, ".hamburger, button.menu, .menu-toggle")
    ]
    for by, sel in menu_selectors:
        try:
            for btn in driver.find_elements(by, sel):
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    break
        except Exception:
            continue

    # Find "Opinión" inside mobile menu
    try:
        el = driver.find_element(
            By.XPATH,
            "//a[contains(text(),'Opinión') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'opinion')]"
        )
        driver.execute_script("arguments[0].click();", el)
        return
    except Exception:
        pass

    # Fallback scan
    for a in driver.find_elements(By.TAG_NAME, "a"):
        t = (a.text or "").lower()
        href = (a.get_attribute("href") or "").lower()
        if "opinion" in t or "/opinion/" in href:
            driver.execute_script("arguments[0].click();", a)
            return

    raise Exception("Could not locate the 'Opinión' navigation link.")


# -------------------------------------------------------------------
# Collect article links
# -------------------------------------------------------------------
def collect_opinion_links(driver, wait, limit=5):
    try:
        elems = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article h2 a")),
            DEFAULT_WAIT
        )
        links = [e.get_attribute("href") for e in elems[:limit] if e.get_attribute("href")]
        if links:
            return links
    except Exception:
        pass

    # fallback
    results = []
    for a in driver.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href") or ""
        if "/opinion/" in href:
            results.append(href)
            if len(results) == limit:
                break

    if not results:
        raise Exception("Could not locate article links on Opinion page.")

    return results[:limit]


# -------------------------------------------------------------------
# Extract article page info
# -------------------------------------------------------------------
def extract_article_data(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Title
    h1 = soup.find("h1")
    title_es = h1.get_text(strip=True) if h1 else None

    # Content
    content = ""
    article = soup.find("article")
    if article:
        ps = article.find_all("p")
        content = "\n\n".join([p.get_text(strip=True) for p in ps])

    # Image (OG)
    og = soup.find("meta", property="og:image")
    image_url = og.get("content") if og else None

    return {
        "title_es": title_es,
        "content_es": content,
        "image_url": image_url
    }


# -------------------------------------------------------------------
# Mark BrowserStack session status
# -------------------------------------------------------------------
def set_status(driver, status, reason):
    try:
        driver.execute_script(
            f'browserstack_executor: {{"action":"setSessionStatus", "arguments": {{"status":"{status}", "reason":"{reason}"}}}}'
        )
    except Exception:
        pass


# -------------------------------------------------------------------
# Main test
# -------------------------------------------------------------------
def run_test(capabilities: Dict[str, Any]):
    driver = None
    results = {"success": False, "items": [], "error": None}

    try:
        driver = build_driver(capabilities)
        wait = WebDriverWait(driver, DEFAULT_WAIT)

        driver.get("https://elpais.com/")
        time.sleep(1)

        quick_accept_cookies(driver)

        click_opinion(driver, wait)

        urls = collect_opinion_links(driver, wait, NUM_ARTICLES)

        for url in urls:
            driver.get(url)
            time.sleep(1)

            data = extract_article_data(driver)
            title_es = data["title_es"] or ""
            title_en = translator.translate(title_es) if title_es else ""

            results["items"].append({
                "url": url,
                "title_es": title_es,
                "title_en": title_en,
                "content_es": data["content_es"],
                "image_url": data["image_url"]
            })

        results["success"] = True
        set_status(driver, "passed", "Scraped all articles successfully")

    except Exception as e:
        results["error"] = str(e)
        results["success"] = False
        if driver:
            set_status(driver, "failed", str(e))

    finally:
        if driver:
            driver.quit()

    return results
