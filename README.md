# Reverse Image OSINT

Multi-service reverse image search tool for OSINT investigations.

## Features

- **Multiple search engines**: Yandex Images, Google Lens, Bing Visual Search
- **Metadata extraction**: EXIF data, GPS coordinates, camera info, MD5
- **URL normalization**: filters weak search-engine pages, deduplicates results
- **OSINT domain scoring**: VK/OK/Telegram/TikTok/Instagram ranked higher
- **Batch processing**: process directory of images with threaded workers
- **JSON reports**: structured output with combined results and top domains
- **CLI**: simple one-image and batch modes

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Install Chrome/Chromium for Selenium
# On Kali: sudo apt install chromium-driver chromium
```

## Quick Start

```bash
# Single image search
python src/osint_search.py /path/to/image.jpg

# Batch processing
python src/batch_search.py /path/to/images/ --workers 2 --max-results 15
```

## Output

Report JSON:
```json
{
  "image": "...",
  "timestamp": "...",
  "md5": "...",
  "metadata": { "format": "JPEG", "width": 480, "height": 275, "exif": {...}, "gps": {...} },
  "summary": { "yandex": {"status":"ok","count":10} },
  "combined": {
    "all_results": ["https://..."],
    "top_domains": [
      {"host":"vk.com","score":20,"url":"https://vk.com/..."},
      {"host":"tgcnt.ru","score":18,"url":"https://tgcnt.ru/..."}
    ]
  }
}
```

## Supported Services

| Service | Method | Notes |
|---------|--------|-------|
| Yandex Images | Selenium | Free, best for RU/EU |
| Google Lens | Selenium | Free, global coverage |
| Bing Visual | Selenium | Free, useful supplement |

## Notes

- Requires Chrome/Chromium and matching chromedriver.
- Google Lens may block some automated uploads; Yandex is currently the most reliable engine.
- Use only for authorized investigations.

## License

MIT
