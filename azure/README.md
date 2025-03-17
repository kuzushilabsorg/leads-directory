# Azure Partner Scraper

This tool scrapes partner information from the Microsoft AppSource marketplace. It handles filtering, pagination, and data extraction from partner cards.

## Features

- Scrape partner data from the Microsoft AppSource marketplace
- Apply filters (e.g., location, capabilities, industries)
- Extract partner information (name, URL, description, logo URL)
- Handle pagination to process all available partners
- Save partner data to JSON files
- Save HTML content for analysis

## Requirements

- Python 3.7+
- Chrome browser installed
- Dependencies listed in `requirements.txt`

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the main script with the desired options:

```bash
python main.py --location "United States" --max-pages 5
```

### Command Line Arguments

- `--output-dir`: Directory where output files will be saved (default: current directory)
- `--location`: Filter by partner location (default: "United States")
- `--max-pages`: Maximum number of pages to scrape (default: all pages)
- `--no-headless`: Run the browser in visible mode (not headless)
- `--chrome-driver-path`: Path to the Chrome driver executable (optional)

## Output

The scraper generates the following output files:

- `partner-dir.html`: HTML content of the partners directory page
- `partner-dir-page-{page_number}.html`: HTML content of each page
- `azure_partners.json`: JSON file containing the extracted partner data

## Architecture

The scraper is built with a modular architecture:

1. **AzurePartnerScraperSelenium**: Main class for scraping partner data using Selenium
2. **PartnerData**: Data class for storing partner information

## Example

```python
from azure_partner_scraper_selenium import AzurePartnerScraperSelenium

# Initialize the scraper
scraper = AzurePartnerScraperSelenium(output_dir="output")

# Scrape partners with location filter
partners = scraper.scrape_partners(location="United States", max_pages=3)

# Save partners to JSON
scraper.save_partners_to_json(partners, "azure_partners.json")
```

## Customization

You can customize the scraper by modifying the following:

- Filter types and values in the `apply_filter` method
- Selectors for partner cards in the `extract_partners_from_page` method
- Selectors for pagination in the `go_to_next_page` method

## Troubleshooting

If you encounter issues:

1. Run with `--no-headless` to see the browser actions
2. Check the log file `azure_partner_scraper.log` for detailed information
3. Inspect the saved HTML files to understand the page structure
