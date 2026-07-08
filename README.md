# Reverse Image OSINT

Multi-service reverse image search tool for OSINT investigations.

## Features

- **Multiple search engines**: Yandex Images, Google Lens, Bing Visual Search, TinEye
- **Metadata extraction**: EXIF data, GPS coordinates, camera info
- **Face detection**: Optional face detection for identifying individuals
- **Batch processing**: Process multiple images at once
- **JSON/HTML reports**: Structured output for investigations
- **Modular architecture**: Easy to add new search engines

## Installation

```bash
pip install -r requirements.txt
# Install Chrome/Chromium for web scraping
# Install Tesseract for OCR if needed
```

## Quick Start

```bash
# Single image search
python src/osint_search.py /path/to/image.jpg

# With metadata extraction
python src/osint_search.py image.jpg --metadata

# Batch processing
python src/batch_search.py /path/to/images/ --output report.json
```

## Configuration

Copy `config/settings.example.json` to `config/settings.json` and add your API keys:

```json
{
  "tineye_api_key": "YOUR_TINEYE_KEY",
  "bing_api_key": "YOUR_BING_KEY"
}
```

## Supported Services

| Service | Method | Notes |
|---------|--------|-------|
| Yandex Images | Selenium | Free, best for RU/EU |
| Google Lens | Playwright | Free, good global coverage |
| Bing Visual | API/Scrape | API key recommended |
| TinEye | API | Free tier available |
| EXIF/Metadata | ExifTool | Local, no API needed |

## Architecture

```
src/
├── osint_search.py      # Main entry point
├── engines/             # Search engine modules
│   ├── yandex.py
│   ├── google.py
│   ├── bing.py
│   └── tineye.py
├── analyzers/           # Image analysis
│   ├── metadata.py
│   └── faces.py
└── reports/             # Report generation
    ├── json_report.py
    └── html_report.py
```

## Legal

Use only for authorized investigations. Respect privacy laws and terms of service of search engines.

## License

MIT
