#!/usr/bin/env python3
"""
Reverse Image OSINT — multi-engine search + metadata extraction.
"""
import os
import sys
import time
import json
import argparse
import hashlib
from datetime import datetime
from urllib.parse import quote_plus

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

try:
    from exifread import process_file
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
from tqdm import tqdm
from colorama import init, Fore, Style

init(autoreset=True)


class ImageMetadata:
    @staticmethod
    def extract(image_path: str) -> dict:
        meta = {"file": image_path, "size": os.path.getsize(image_path)}
        try:
            with Image.open(image_path) as img:
                meta["format"] = img.format
                meta["mode"] = img.mode
                meta["width"] = img.width
                meta["height"] = img.height
                meta["aspect_ratio"] = round(img.width / img.height, 3) if img.height else None
        except Exception as e:
            meta["error"] = str(e)
            return meta

        # EXIF via Pillow
        try:
            exif = img._getexif()
            if exif:
                tags = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    tags[str(tag)] = str(value)
                meta["exif"] = tags
        except Exception:
            pass

        # EXIF via exifread for detailed GPS/MakerNotes
        if HAS_EXIFREAD:
            try:
                with open(image_path, "rb") as f:
                    tags = process_file(f, details=False)
                    gps = {}
                    for tag, value in tags.items():
                        tag_name = tag.split(" ")[-1]
                        if "GPS" in tag:
                            gps[tag_name] = str(value)
                    if gps:
                        meta["gps"] = gps
            except Exception:
                pass

        return meta

    @staticmethod
    def md5(image_path: str) -> str:
        h = hashlib.md5()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


class YandexSearch:
    NAME = "yandex"

    def __init__(self, headless=True):
        self.opts = Options()
        self.opts.add_argument("--headless=new")
        self.opts.add_argument("--no-sandbox")
        self.opts.add_argument("--disable-dev-shm-usage")
        self.opts.add_argument("--disable-gpu")
        self.opts.add_argument("--window-size=1280,900")
        self.opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36")

    def search(self, image_path: str, max_results=30) -> dict:
        driver = webdriver.Chrome(options=self.opts)
        results = []
        errors = []
        try:
            print(Fore.CYAN + f"[{self.NAME.upper()}] Opening Yandex Images...")
            driver.get("https://yandex.com/images/")
            wait = WebDriverWait(driver, 20)

            try:
                upload_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.CbirUploadBtn, button[data-type="cbir"]')))
                upload_btn.click()
            except Exception as e:
                errors.append(f"upload_btn_click_failed: {e}")
                print(Fore.YELLOW + f"[{self.NAME.upper()}] Upload btn failed: {e}")

            time.sleep(2)
            try:
                file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                file_input.send_keys(os.path.abspath(image_path))
                print(Fore.GREEN + f"[{self.NAME.upper()}] Image uploaded")
            except Exception as e:
                errors.append(f"file_input_send_failed: {e}")
                print(Fore.RED + f"[{self.NAME.upper()}] File input failed: {e}")

            time.sleep(10)

            # Collect links
            links = driver.find_elements(By.CSS_SELECTOR, 'a.Link, a[href*="http"]')
            seen = set()
            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith("http") and href not in seen:
                    seen.add(href)
                    results.append(href)
                    if len(results) >= max_results:
                        break

            # Collect page text for inspection
            try:
                title = driver.title
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, "html.parser")
                text_snippets = [s.strip() for s in soup.stripped_strings if len(s.strip()) > 20][:20]
            except Exception:
                title = ""
                text_snippets = []

        except Exception as e:
            errors.append(f"fatal: {str(e)}")
            print(Fore.RED + f"[{self.NAME.upper()}] Fatal: {e}")
        finally:
            driver.quit()

        return {
            "engine": self.NAME,
            "status": "ok" if results else "empty",
            "results_count": len(results),
            "results": results,
            "title": title if 'title' in dir() else "",
            "text_snippets": text_snippets if 'text_snippets' in dir() else [],
            "errors": errors,
        }


class GoogleLensSearch:
    NAME = "google_lens"

    def __init__(self, headless=True):
        self.opts = Options()
        self.opts.add_argument("--headless=new")
        self.opts.add_argument("--no-sandbox")
        self.opts.add_argument("--disable-dev-shm-usage")
        self.opts.add_argument("--disable-gpu")
        self.opts.add_argument("--window-size=1280,900")
        self.opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36")

    def search(self, image_path: str, max_results=30) -> dict:
        driver = webdriver.Chrome(options=self.opts)
        results = []
        errors = []
        try:
            print(Fore.CYAN + f"[{self.NAME.upper()}] Opening Google Lens...")
            driver.get("https://lens.google.com/")
            wait = WebDriverWait(driver, 20)

            time.sleep(3)
            upload_xpath = "//input[@type='file']"
            try:
                file_input = driver.find_element(By.XPATH, upload_xpath)
                file_input.send_keys(os.path.abspath(image_path))
                print(Fore.GREEN + f"[{self.NAME.upper()}] Image uploaded")
            except Exception as e:
                errors.append(f"file_input_send_failed: {e}")
                print(Fore.YELLOW + f"[{self.NAME.upper()}] File input failed: {e}")

            time.sleep(12)

            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="http"]')
            seen = set()
            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith("http") and href not in seen:
                    seen.add(href)
                    results.append(href)
                    if len(results) >= max_results:
                        break

            title = driver.title
            soup = BeautifulSoup(driver.page_source, "html.parser")
            text_snippets = [s.strip() for s in soup.stripped_strings if len(s.strip()) > 20][:20]
        except Exception as e:
            errors.append(f"fatal: {str(e)}")
            print(Fore.RED + f"[{self.NAME.upper()}] Fatal: {e}")
        finally:
            driver.quit()

        return {
            "engine": self.NAME,
            "status": "ok" if results else "empty",
            "results_count": len(results),
            "results": results,
            "title": title if 'title' in dir() else "",
            "text_snippets": text_snippets if 'text_snippets' in dir() else [],
            "errors": errors,
        }


class BingVisualSearch:
    NAME = "bing"

    def __init__(self, headless=True):
        self.opts = Options()
        self.opts.add_argument("--headless=new")
        self.opts.add_argument("--no-sandbox")
        self.opts.add_argument("--disable-dev-shm-usage")
        self.opts.add_argument("--disable-gpu")
        self.opts.add_argument("--window-size=1280,900")
        self.opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36")

    def search(self, image_path: str, max_results=30) -> dict:
        driver = webdriver.Chrome(options=self.opts)
        results = []
        errors = []
        try:
            print(Fore.CYAN + f"[{self.NAME.upper()}] Opening Bing Visual Search...")
            driver.get("https://www.bing.com/visualsearch")
            wait = WebDriverWait(driver, 20)

            time.sleep(3)
            try:
                file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                file_input.send_keys(os.path.abspath(image_path))
                print(Fore.GREEN + f"[{self.NAME.upper()}] Image uploaded")
            except Exception as e:
                errors.append(f"file_input_send_failed: {e}")
                print(Fore.YELLOW + f"[{self.NAME.upper()}] File input failed: {e}")

            time.sleep(12)

            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="http"]')
            seen = set()
            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith("http") and href not in seen:
                    seen.add(href)
                    results.append(href)
                    if len(results) >= max_results:
                        break

            title = driver.title
            soup = BeautifulSoup(driver.page_source, "html.parser")
            text_snippets = [s.strip() for s in soup.stripped_strings if len(s.strip()) > 20][:20]
        except Exception as e:
            errors.append(f"fatal: {str(e)}")
            print(Fore.RED + f"[{self.NAME.upper()}] Fatal: {e}")
        finally:
            driver.quit()

        return {
            "engine": self.NAME,
            "status": "ok" if results else "empty",
            "results_count": len(results),
            "results": results,
            "title": title if 'title' in dir() else "",
            "text_snippets": text_snippets if 'text_snippets' in dir() else [],
            "errors": errors,
        }


def run_search(image_path: str, engines=None, max_results=30):
    if engines is None:
        engines = ["yandex", "google_lens", "bing"]

    report = {
        "image": os.path.abspath(image_path),
        "timestamp": datetime.now().isoformat(),
        "md5": ImageMetadata.md5(image_path),
        "metadata": ImageMetadata.extract(image_path),
        "engines": [],
        "summary": {}
    }

    searchers = {
        "yandex": YandexSearch,
        "google_lens": GoogleLensSearch,
        "bing": BingVisualSearch,
    }

    print(Fore.MAGENTA + Style.BRIGHT + f"\n=== Reverse Image OSINT ===")
    print(Fore.MAGENTA + f"Image: {image_path}")
    print(Fore.MAGENTA + f"MD5: {report['md5']}\n")

    for engine_name in engines:
        cls = searchers.get(engine_name)
        if not cls:
            print(Fore.YELLOW + f"[SKIP] Unknown engine: {engine_name}")
            continue
        try:
            engine = cls()
            res = engine.search(image_path, max_results=max_results)
            report["engines"].append(res)
            report["summary"][engine_name] = {
                "status": res.get("status"),
                "count": res.get("results_count"),
                "errors": res.get("errors"),
            }
        except Exception as e:
            print(Fore.RED + f"[{engine_name.upper()}] Exception: {e}")
            report["engines"].append({"engine": engine_name, "status": "error", "error": str(e)})

    return report


def main():
    parser = argparse.ArgumentParser(description="Reverse Image OSINT multi-engine search")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--engines", nargs="+", default=["yandex", "google_lens", "bing"], help="Engines to run")
    parser.add_argument("--max-results", type=int, default=30, help="Max results per engine")
    parser.add_argument("--output", help="Output JSON file path")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(Fore.RED + f"File not found: {args.image}")
        sys.exit(1)

    report = run_search(args.image, engines=args.engines, max_results=args.max_results)

    output_path = args.output or f"/home/kali/capture/osint/osint_{int(time.time())}.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(Fore.GREEN + Style.BRIGHT + f"\n[+] Report saved: {output_path}")
    print(Fore.GREEN + f"Engines run: {', '.join(args.engines)}")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
