#!/usr/bin/env python3
"""
Batch reverse image search across multiple images.
"""
import os
import sys
import time
import json
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import os as _os
import sys as _sys
_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)
from osint_search import ImageMetadata, YandexSearch, GoogleLensSearch, BingVisualSearch, run_search


def batch_search(folder: str, engines=None, max_results=20, output=None, workers=2):
    if engines is None:
        engines = ["yandex"]

    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
    files = sorted(
        f
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in exts
    )

    if not files:
        print("No images found in", folder)
        return

    print(f"Found {len(files)} images in {folder}")

    output_path = output or f"/home/kali/capture/osint/batch_{int(time.time())}.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    batch_report = {
        "folder": os.path.abspath(folder),
        "timestamp": datetime.now().isoformat(),
        "total_images": len(files),
        "engines": engines,
        "images": [],
    }

    def process(path):
        image_path = os.path.join(folder, path)
        try:
            report = run_search(image_path, engines=engines, max_results=max_results)
            return path, report
        except Exception as e:
            return path, {"error": str(e), "image": image_path}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process, f): f for f in files}
        for future in as_completed(futures):
            path, report = future.result()
            batch_report["images"].append(report)
            print(f"[{len(batch_report['images'])}/{len(files)}] {path}: {report.get('summary', {})}")

    with open(output_path, "w") as f:
        json.dump(batch_report, f, indent=2, ensure_ascii=False)

    print(f"\nBatch report saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Batch reverse image OSINT search")
    parser.add_argument("folder", help="Folder with images")
    parser.add_argument("--engines", nargs="+", default=["yandex"], help="Engines to run")
    parser.add_argument("--max-results", type=int, default=20, help="Max results per image")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--workers", type=int, default=2, help="Parallel workers")
    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        print("Folder not found:", args.folder)
        sys.exit(1)

    batch_search(args.folder, engines=args.engines, max_results=args.max_results, output=args.output, workers=args.workers)


if __name__ == "__main__":
    main()
