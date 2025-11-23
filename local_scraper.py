from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from PIL import Image
from io import BytesIO
import requests
import os
import time
import sys
from collections import Counter
import re

print("--------------START--------------\n")

translator = GoogleTranslator(source="es", target="en")
os.makedirs("article_images", exist_ok=True)




# Lists to store titles
spanish_titles = []
english_titles = []




# Chrome options for faster, stable browsing
options = webdriver.ChromeOptions()
options.add_argument("--lang=es-ES")
options.add_argument("--window-size=1920,1080")




#starting browser
driver = webdriver.Chrome(options=options)  
#Setting wait time to be 15 seconds
wait = WebDriverWait(driver, 15) 





#Retry getting web-page 3 times if Selenium fails to fetch 
def safe_get(url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(url)
            return True
        except:
            print(f"Loading failed, retry {attempt+1}/{retries}...")
            time.sleep(2)
    return False




try:

    #Open El Pais
    safe_get("https://elpais.com/")
    time.sleep(3)




    # Accept cookies if popup appears
    try:
        accept_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Aceptar')]"))
        )
        accept_btn.click()
        print("Cookies accepted")
        time.sleep(1)
    except:
        pass





    # Find the 'Opinion' Section, Click its link (JavaScript) and wait 3sec for loading
    print("\nNavigating to Opinion")
    opinion_btn = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//a[contains(translate(text(),'OPINIÓN','opinión'),'opinión')]")
        )
    )
    driver.execute_script("arguments[0].click();", opinion_btn)
    time.sleep(3)






    # Collect first 5 article links
    article_links = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article h2 a"))
    )[:5]
    article_urls = [a.get_attribute("href") for a in article_links]
    print(f"Article Found {len(article_urls)} articles\n")




    

    # Process each article
    for index, url in enumerate(article_urls, start=1):
        print(f"\n==============================")
        print(f"ARTICLE {index}/5")
        print("==============================")

        if not safe_get(url):
            print("Failed → Skipping")
            continue

        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Extract Spanish title
        title_tag = soup.find("h1")
        if not title_tag:
            print("Missing title")
            continue

        title_es = title_tag.get_text(strip=True)
        spanish_titles.append(title_es)
        print(f"Spanish Title:\n{title_es}")

        # Extract image (OG image first)
        img_url = None
        og_image = soup.find("meta", property="og:image")
        if og_image:
            img_url = og_image.get("content")

        if img_url:
            try:
                img_data = requests.get(img_url, timeout=15).content
                img = Image.open(BytesIO(img_data)).convert("RGB")
                img_path = f"article_images/article_{index}.png"
                img.save(img_path, "PNG")
                print(f"Image saved → {img_path}")
            except Exception as e:
                print(f"Image download failed: {e}")

        # Translate title to English
        try:
            title_en = translator.translate(title_es)
            english_titles.append(title_en)
            print(f"English Translation:\n{title_en}")
        except:
            print("Translation failed.")
        print("\n──────────────────────────────")




    # ---------------------------
    # WORD FREQUENCY ANALYSIS IN ENGLISH TITLES
    # ---------------------------
    print("\nRepeated Words in English Titles\n")

    all_words = []
    for title in english_titles:
        words = re.findall(r"\b[a-z']+\b", title.lower())
        all_words.extend(words)

    counter = Counter(all_words)
    repeated_words = {word: count for word, count in counter.items() if count >= 2}

    if repeated_words:
        print("Words repeated ≥ 2 times:")
        for word, freq in sorted(repeated_words.items(), key=lambda x: x[1], reverse=True):
            print(f"   • '{word}' → {freq} times")
    else:
        print("No English words repeated ≥ 2 times.")

    print("\nCompleted Successfully!")

except Exception as e:
    print(f"\nError: {e}")

finally:
    print("\nClosing browser...")
    driver.quit()
