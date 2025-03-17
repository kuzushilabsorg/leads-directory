#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to run the Azure Partner Scraper with robust features:
- Rate limiting with random delays
- Checkpoint saving
- Error handling
- Resumable processing
"""

import os
import json
import time
import random
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

from azure_partner_scraper_selenium import AzurePartnerScraperSelenium, PartnerData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("azure_scraper_run.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("azure_scraper_runner")

class AzureScraperRunner:
    """
    Runner for the Azure Partner Scraper with robust features.
    """
    
    def __init__(
        self, 
        output_dir: str = "output", 
        checkpoint_interval: int = 10,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        max_pages: int = 100,
        headless: bool = False
    ):
        """
        Initialize the Azure Scraper Runner.
        
        Args:
            output_dir: Directory to save output files
            checkpoint_interval: Number of pages after which to save a checkpoint
            min_delay: Minimum delay between page loads (seconds)
            max_delay: Maximum delay between page loads (seconds)
            max_pages: Maximum number of pages to scrape
            headless: Whether to run the browser in headless mode
        """
        self.output_dir = output_dir
        self.checkpoint_interval = checkpoint_interval
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_pages = max_pages
        self.headless = headless
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize scraper
        self.scraper = None
        
        # Initialize state
        self.partners = []
        self.current_page = 0
        self.total_pages_scraped = 0
        self.start_time = None
        self.checkpoint_path = os.path.join(output_dir, "azure_scraper_checkpoint.json")
    
    def _random_delay(self) -> None:
        """Add a random delay between operations to avoid rate limiting."""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.info(f"Waiting for {delay:.2f} seconds...")
        time.sleep(delay)
    
    def _save_checkpoint(self) -> None:
        """Save the current state as a checkpoint."""
        checkpoint_data = {
            "timestamp": datetime.now().isoformat(),
            "current_page": self.current_page,
            "total_pages_scraped": self.total_pages_scraped,
            "partners_count": len(self.partners),
            "runtime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }
        
        with open(self.checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        logger.info(f"Checkpoint saved: {self.checkpoint_path}")
    
    def _save_partners(self, filename: str = None) -> None:
        """Save the partners data to a JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"azure_partners_{timestamp}.json"
        
        output_path = os.path.join(self.output_dir, filename)
        
        # Convert partners to dictionaries
        partners_data = [partner.to_dict() for partner in self.partners]
        
        with open(output_path, 'w') as f:
            json.dump(partners_data, f, indent=2)
        
        logger.info(f"Saved {len(self.partners)} partners to {output_path}")
        return output_path
    
    def _load_checkpoint(self) -> bool:
        """
        Load the checkpoint if it exists.
        
        Returns:
            True if checkpoint was loaded, False otherwise
        """
        if not os.path.exists(self.checkpoint_path):
            logger.info("No checkpoint found, starting from scratch")
            return False
        
        try:
            with open(self.checkpoint_path, 'r') as f:
                checkpoint_data = json.load(f)
            
            self.current_page = checkpoint_data.get("current_page", 0)
            self.total_pages_scraped = checkpoint_data.get("total_pages_scraped", 0)
            
            logger.info(f"Loaded checkpoint: resuming from page {self.current_page}")
            logger.info(f"Previously scraped {checkpoint_data.get('partners_count', 0)} partners")
            
            # Load existing partners if available
            partners_files = [f for f in os.listdir(self.output_dir) if f.startswith("azure_partners_") and f.endswith(".json")]
            if partners_files:
                # Get the most recent file
                latest_file = max(partners_files, key=lambda f: os.path.getmtime(os.path.join(self.output_dir, f)))
                partners_path = os.path.join(self.output_dir, latest_file)
                
                with open(partners_path, 'r') as f:
                    partners_data = json.load(f)
                
                # Convert dictionaries back to PartnerData objects
                self.partners = [PartnerData(**partner) for partner in partners_data]
                logger.info(f"Loaded {len(self.partners)} partners from {partners_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            logger.info("Starting from scratch")
            return False
    
    def run(self, filters: Dict[str, str] = None, url: str = None) -> str:
        """
        Run the Azure Partner Scraper.
        
        Args:
            filters: Dictionary of filters to apply (e.g., {"location": "United States", "capability": "AI"})
            url: URL to start scraping from (if None, use the default URL)
        
        Returns:
            Path to the output file
        """
        self.start_time = datetime.now()
        logger.info(f"Starting Azure Partner Scraper at {self.start_time}")
        
        # Initialize the scraper
        try:
            self.scraper = AzurePartnerScraperSelenium(headless=self.headless)
            
            # Load the partners directory page
            if url:
                self.scraper.load_url(url)
            else:
                self.scraper.load_partners_directory()
            
            # Apply filters if provided
            if filters:
                for filter_type, filter_value in filters.items():
                    self.scraper.apply_filter(filter_type, filter_value)
                    self._random_delay()
            
            # Load checkpoint if it exists
            checkpoint_loaded = self._load_checkpoint()
            
            # If checkpoint was loaded and we're not on the first page, navigate to the current page
            if checkpoint_loaded and self.current_page > 0:
                logger.info(f"Navigating to page {self.current_page}")
                
                # Navigate to the current page
                for _ in range(self.current_page):
                    if not self.scraper.go_to_next_page():
                        logger.warning("Could not navigate to the saved page, starting from current page")
                        break
                    self._random_delay()
            
            # Start scraping
            more_pages = True
            while more_pages and self.total_pages_scraped < self.max_pages:
                try:
                    # Extract partners from the current page
                    page_partners = self.scraper.extract_partners_from_page()
                    logger.info(f"Extracted {len(page_partners)} partners from page {self.current_page + 1}")
                    
                    # Add to the list of partners
                    self.partners.extend(page_partners)
                    
                    # Increment counters
                    self.current_page += 1
                    self.total_pages_scraped += 1
                    
                    # Save checkpoint if needed
                    if self.total_pages_scraped % self.checkpoint_interval == 0:
                        self._save_checkpoint()
                        self._save_partners()
                    
                    # Go to the next page
                    more_pages = self.scraper.go_to_next_page()
                    
                    # Add random delay
                    if more_pages:
                        self._random_delay()
                
                except Exception as e:
                    logger.error(f"Error scraping page {self.current_page + 1}: {e}")
                    # Save checkpoint and partners before exiting
                    self._save_checkpoint()
                    self._save_partners()
                    raise
            
            # Save final results
            logger.info(f"Scraping completed. Scraped {self.total_pages_scraped} pages and found {len(self.partners)} partners")
            output_path = self._save_partners()
            
            # Clean up
            self.scraper.close()
            
            # Calculate runtime
            runtime = (datetime.now() - self.start_time).total_seconds()
            logger.info(f"Total runtime: {runtime:.2f} seconds")
            
            return output_path
        
        except Exception as e:
            logger.error(f"Error running Azure Partner Scraper: {e}")
            if self.scraper:
                self.scraper.close()
            raise
    
def main():
    """Main function to run the Azure Partner Scraper."""
    parser = argparse.ArgumentParser(description="Run the Azure Partner Scraper")
    
    parser.add_argument("--output-dir", type=str, default="output", 
                        help="Directory to save output files")
    parser.add_argument("--checkpoint-interval", type=int, default=10, 
                        help="Number of pages after which to save a checkpoint")
    parser.add_argument("--min-delay", type=float, default=1.0, 
                        help="Minimum delay between page loads (seconds)")
    parser.add_argument("--max-delay", type=float, default=3.0, 
                        help="Maximum delay between page loads (seconds)")
    parser.add_argument("--max-pages", type=int, default=100, 
                        help="Maximum number of pages to scrape")
    parser.add_argument("--headless", action="store_true", 
                        help="Run the browser in headless mode")
    parser.add_argument("--filter", type=str, action="append", nargs=2, 
                        metavar=("TYPE", "VALUE"), 
                        help="Filter to apply (e.g., --filter location 'United States')")
    parser.add_argument("--url", type=str, 
                        help="URL to start scraping from")
    
    args = parser.parse_args()
    
    # Convert filters to dictionary
    filters = {}
    if args.filter:
        for filter_type, filter_value in args.filter:
            filters[filter_type] = filter_value
    
    # Create and run the scraper
    runner = AzureScraperRunner(
        output_dir=args.output_dir,
        checkpoint_interval=args.checkpoint_interval,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        max_pages=args.max_pages,
        headless=args.headless
    )
    
    try:
        output_path = runner.run(filters=filters, url=args.url)
        logger.info(f"Scraping completed successfully. Results saved to {output_path}")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
