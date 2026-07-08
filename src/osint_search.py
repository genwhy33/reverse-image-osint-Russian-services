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

from PIL import Image
from PIL.ExifTags import TAGS

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
from colorama import init, Fore, Style

from analyzers import normalize_results, domain_summary

init(autoreset=True)


def get_image_resolution(path: str):
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


class ImageMetadata:
    @staticmethod
    def extract(image_path: str) -> dict:
        meta = {"file": image_path, "size": os.path.getsize(image_path)}
        w, h = get_image_resolution(image_path)
        meta.update({"width": w, "height": h, "aspect_ratio": round(w/h, 3) if h else None})
        try:
            with Image.open(image_path) as img:
                meta.update({"format": getattr(img, "format", None), "mode": getattr(img, "mode", None)})
                exif = img._getexif()
                if exif:
                    meta["exif"] = {str(TAGS.get(t, t)): str(v) for t, v in exif.items()}
        except Exception:
            pass
        if HAS_EXIFREAD:
            try:
                with open(image_path, "rb") as f:
                    tags = process_file(f, details=False)
                    gps = {tag.split(" ")[-1]: str(v) for tag, v in tags.items() if "GPS" in tag}
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


class BaseSearch:
    def __init__(self, headless=True):
        self.opts = Options()
        self.opts.add_argument("--headless=new")
        self.opts.add_argument("--no-sandbox")
        self.opts.add_argument("--disable-dev-shm-usage")
        self.opts.add_argument("--disable-gpu")
        self.opts.add_argument("--window-size=1280,900")
        self.opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36")

    def _collect(self, driver, max_results=30):
        raw = []
        seen = set()
        for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="http"]'):
            href = link.get_attribute("href")
            if href and href.startswith("http") and href not in seen:
                seen.add(href)
                raw.append(href)
        return normalize_results(raw, max_results=max_results)

    def _page_snapshot(self, driver):
        try:
            title = driver.title
            soup = BeautifulSoup(driver.page_source, "html.parser")
            snippets = [s.strip() for s in soup.stripped_strings if len(s.strip()) > 20][:20]
        except Exception:
            title, snippets = "", []
        return title, snippets


class YandexSearch(BaseSearch):
    NAME = "yandex"

    def search(self, image_path: str, max_results=30) -> dict:
        driver = webdriver.Chrome(options=self.opts)
        errors = []
        try:
            print(Fore.CYAN + f"[{self.NAME.upper()}] Open Yandex Images...")
            driver.get("https://yandex.com/images/")
            wait = WebDriverWait(driver, 20)
            try:
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.CbirUploadBtn, button[data-type="cbir"]'))).click()
            except Exception as e:
                errors.append(f"upload_btn_click_failed: {e}")
                print(Fore.YELLOW + f"[{self.NAME.upper()}] Upload btn failed: {e}")
            time.sleep(2)
            try:
                driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys(os.path.abspath(image_path))
                print(Fore.GREEN + f"[{self.NAME.upper()}] Image uploaded")
            except Exception as e:
                errors.append(f"file_input_send_failed: {e}")
                print(Fore.RED + f"[{self.NAME.upper()}] File input failed: {e}")
            time.sleep(10)
            results = self._collect(driver, max_results=max_results)
            title, text_snippets = self._page_snapshot(driver)
        except Exception as e:
            errors.append(f"fatal: {str(e)}")
            print(Fore.RED + f"[{self.NAME.upper()}] Fatal: {e}")
            results = []
            title, text_snippets = "", []
        finally:
            driver.quit()
        return {"engine": self.NAME, "status": "ok" if results else "empty", "results_count": len(results), "results": results, "title": title, "text_snippets": text_snippets, "errors": errors}


class GoogleLensSearch(BaseSearch):
    NAME = "google_lens"

    def search(self, image_path: str, max_results=30) -> dict:
        driver = webdriver.Chrome(options=self.opts)
        errors = []
        try:
            print(Fore.CYAN + f"[{self.NAME.upper()}] Open Google Lens...")
            driver.get("https://lens.google.com/")
            time.sleep(3)
            try:
                driver.find_element(By.XPATH, "//input[@type='file']").send_keys(os.path.abspath(image_path))
                print(Fore.GREEN + f"[{self.NAME.upper()}] Image uploaded")
            except Exception as e:
                errors.append(f"file_input_send_failed: {e}")
                print(Fore.YELLOW + f"[{self.NAME.upper()}] File input failed: {e}")
            time.sleep(12)
            results = self._collect(driver, max_results=max_results)
            title, text_snippets = self._page_snapshot(driver)
        except Exception as e:
            errors.append(f"fatal: {str(e)}")
            print(Fore.RED + f"[{self.NAME.upper()}] Fatal: {e}")
            results = []
            title, text_snippets = "", []
        finally:
            driver.quit()
        return {"engine": self.NAME, "status": "ok" if results else "empty", "results_count": len(results), "results": results, "title": title, "text_snippets": text_snippets, "errors": errors}


class BingVisualSearch(BaseSearch):
    NAME = "bing"

    def search(self, image_path: str, max_results=30) -> dict:
        driver = webdriver.Chrome(options=self.opts)
        errors = []
        try:
            print(Fore.CYAN + f"[{self.NAME.upper()}] Open Bing Visual Search...")
            driver.get("https://www.bing.com/visualsearch")
            time.sleep(3)
            try:
                driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys(os.path.abspath(image_path))
                print(Fore.GREEN + f"[{self.NAME.upper()}] Image uploaded")
            except Exception as e:
                errors.append(f"file_input_send_failed: {e}")
                print(Fore.YELLOW + f"[{self.NAME.upper()}] File input failed: {e}")
            time.sleep(12)
            results = self._collect(driver, max_results=max_results)
            title, text_snippets = self._page_snapshot(driver)
        except Exception as e:
            errors.append(f"fatal: {str(e)}")
            print(Fore.RED + f"[{self.NAME.upper()}] Fatal: {e}")
            results = []
            title, text_snippets = "", []
        finally:
            driver.quit()
        return {"engine": self.NAME, "status": "ok" if results else "empty", "results_count": len(results), "results": results, "title": title, "text_snippets": text_snippets, "errors": errors}


def run_search(image_path: str, engines=None, max_results=30):
    if engines is None:
        engines = ["yandex", "google_lens", "bing"]

    report = {
        "image": os.path.abspath(image_path),
        "timestamp": datetime.now().isoformat(),
        "md5": ImageMetadata.md5(image_path),
        "metadata": ImageMetadata.extract(image_path),
        "engines": [],
        "summary": {},
        "combined": {"all_results": [], "top_domains": []},
    }

    searchers = {"yandex": YandexSearch, "google_lens": GoogleLensSearch, "bing": BingVisualSearch}

    print(Fore.MAGENTA + Style.BRIGHT + f"\n=== Reverse Image OSINT ===")
    print(Fore.MAGENTA + f"Image: {image_path}")
    print(Fore.MAGENTA + f"MD5: {report['md5']}\n")

    merged: list[str] = []
    for engine_name in engines:
        cls = searchers.get(engine_name)
        if not cls:
            print(Fore.YELLOW + f"[SKIP] Unknown engine: {engine_name}")
            continue
        try:
            res = cls().search(image_path, max_results=max_results)
            report["engines"].append(res)
            report["summary"][engine_name] = {"status": res.get("status"), "count": res.get("results_count"), "errors": res.get("errors")}
            merged.extend(res.get("results", []))
        except Exception as e:
            print(Fore.RED + f"[{engine_name.upper()}] Exception: {e}")
            report["engines"].append({"engine": engine_name, "status": "error", "error": str(e)})

    report["combined"]["all_results"] = list(dict.fromkeys(merged))
    report["combined"]["top_domains"] = domain_summary(report["combined"]["all_results"])[:50]
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
    print(Fore.GREEN + f"Unique results: {len(report['combined']['all_results'])}")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(Fore.YELLOW + "Top domains:")
    for row in report["combined"]["top_domains"][:15]:
        print(" ", row["score"], row["host"], "->", row["url"])


if __name__ == "__main__":
    main()
