"""
Azure Partner Directory Scraper

This script scrapes partner information from the Microsoft AppSource marketplace.
It uses Selenium to handle JavaScript-rendered content, apply filters, and extract partner data.
"""
import argparse
import json
import logging
import os
import sys
from typing import List

from azure_partner_scraper_selenium import AzurePartnerScraperSelenium, PartnerData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("azure_partner_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Scrape Azure partners from Microsoft AppSource')
    
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Directory where output files will be saved')
    parser.add_argument('--location', type=str, default='United States',
                        help='Filter by partner location')
    parser.add_argument('--max-pages', type=int, default=None,
                        help='Maximum number of pages to scrape (default: all pages)')
    parser.add_argument('--no-headless', action='store_true',
                        help='Run the browser in visible mode (not headless)')
    parser.add_argument('--chrome-driver-path', type=str, default=None,
                        help='Path to the Chrome driver executable')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Delay between browser actions in seconds (default: 2.0)')
    parser.add_argument('--capabilities', type=str, default=None,
                        help='Filter by partner capabilities (comma-separated)')
    parser.add_argument('--industries', type=str, default=None,
                        help='Filter by partner industries (comma-separated)')
    parser.add_argument('--output-file', type=str, default='azure_partners.json',
                        help='Filename for the JSON output (default: azure_partners.json)')
    
    return parser.parse_args()

def main():
    """Main function to run the scraper."""
    args = parse_arguments()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize the scraper
    scraper = AzurePartnerScraperSelenium(
        output_dir=args.output_dir,
        delay_between_actions=args.delay,
        headless=not args.no_headless,
        chrome_driver_path=args.chrome_driver_path
    )
    
    try:
        # Parse filter values
        capabilities = args.capabilities.split(',') if args.capabilities else None
        industries = args.industries.split(',') if args.industries else None
        
        # Scrape partners
        logger.info(f"Scraping partners with location filter: {args.location}")
        partners = scraper.scrape_partners(
            location=args.location,
            capabilities=capabilities,
            industries=industries,
            max_pages=args.max_pages
        )
        
        # Log results
        logger.info(f"Scraped {len(partners)} partners")
        
        # Save partners to JSON
        output_path = os.path.join(args.output_dir, args.output_file)
        scraper.save_partners_to_json(partners, output_path)
        
    except Exception as e:
        logger.error(f"Error scraping partners: {e}")
        sys.exit(1)
    finally:
        # Clean up
        scraper._close_driver()

if __name__ == "__main__":
    main()
