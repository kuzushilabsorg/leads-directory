"""
Azure Partner Scraper

This module provides functionality to scrape partner information from the Microsoft AppSource
marketplace. It handles filtering, pagination, and data extraction.

Classes:
    AzurePartnerScraper: Main class for scraping partner data from AppSource
    PartnerData: Data class for storing partner information
"""
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("azure_partner_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("azure_partner_scraper")

@dataclass
class PartnerData:
    """Data class for storing partner information extracted from AppSource."""
    name: str
    url: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    location: Optional[str] = None
    capabilities: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the partner data to a dictionary."""
        return asdict(self)


class AzurePartnerScraper:
    """
    Scraper for Azure partners from Microsoft AppSource marketplace.
    
    This class handles:
    - Fetching HTML content from the partners directory
    - Applying filters (location, capabilities, etc.)
    - Extracting partner data from the page
    - Handling pagination to process all available partners
    """
    
    BASE_URL = "https://appsource.microsoft.com/en-us/marketplace/partner-dir"
    
    def __init__(self, output_dir: str = ".", delay_between_requests: float = 1.0):
        """
        Initialize the Azure Partner Scraper.
        
        Args:
            output_dir: Directory where output files will be saved
            delay_between_requests: Time to wait between HTTP requests (in seconds)
        """
        self.output_dir = output_dir
        self.delay = delay_between_requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
    def fetch_page_content(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Fetch HTML content from the specified URL.
        
        Args:
            url: URL to fetch
            params: Optional query parameters
            
        Returns:
            HTML content as string
        """
        logger.info(f"Fetching content from: {url}")
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            raise
    
    def save_html_content(self, content: str, filename: str) -> None:
        """
        Save HTML content to a file.
        
        Args:
            content: HTML content to save
            filename: Name of the file to save content to
        """
        filepath = os.path.join(self.output_dir, filename)
        logger.info(f"Saving HTML content to: {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def apply_filters(self, location: Optional[str] = None, 
                     capabilities: Optional[List[str]] = None,
                     industries: Optional[List[str]] = None,
                     customer_size: Optional[List[str]] = None,
                     solutions: Optional[List[str]] = None,
                     products: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate filter parameters for the AppSource marketplace.
        
        Args:
            location: Filter by partner location
            capabilities: Filter by partner capabilities
            industries: Filter by industries
            customer_size: Filter by Microsoft customer size
            solutions: Filter by solution categories
            products: Filter by products
            
        Returns:
            Dictionary of query parameters
        """
        params = {}
        
        # Add filters to params if they are provided
        if location:
            params['location'] = location
            
        # Add other filters as needed
        # Note: The actual parameter names will need to be determined by analyzing the site
        
        return params
    
    def extract_partners_from_html(self, html_content: str) -> List[PartnerData]:
        """
        Extract partner data from HTML content.
        
        Args:
            html_content: HTML content of the partners directory page
            
        Returns:
            List of PartnerData objects
        """
        partners = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # This is a placeholder - the actual selectors will need to be determined
        # by analyzing the HTML structure of the partner cards
        partner_cards = soup.select('.partner-card')  # This selector needs to be updated
        
        for card in partner_cards:
            try:
                # Extract data from the card - these selectors need to be updated
                name = card.select_one('.partner-name').text.strip()
                url = card.select_one('a')['href']
                description = card.select_one('.partner-description').text.strip()
                logo_url = card.select_one('img')['src']
                
                # Create PartnerData object and add to list
                partner = PartnerData(
                    name=name,
                    url=url,
                    description=description,
                    logo_url=logo_url
                )
                partners.append(partner)
                
            except Exception as e:
                logger.error(f"Error extracting partner data: {e}")
                continue
                
        return partners
    
    def get_next_page_url(self, html_content: str) -> Optional[str]:
        """
        Extract the URL for the next page from the HTML content.
        
        Args:
            html_content: HTML content of the current page
            
        Returns:
            URL of the next page, or None if there is no next page
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # This is a placeholder - the actual selector will need to be determined
        next_button = soup.select_one('.next-page')  # This selector needs to be updated
        
        if next_button and not next_button.get('disabled'):
            return next_button.get('href')
        
        return None
    
    def save_partners_to_json(self, partners: List[PartnerData], filename: str) -> None:
        """
        Save partner data to a JSON file.
        
        Args:
            partners: List of PartnerData objects
            filename: Name of the file to save data to
        """
        filepath = os.path.join(self.output_dir, filename)
        logger.info(f"Saving {len(partners)} partners to: {filepath}")
        
        # Convert PartnerData objects to dictionaries
        partners_data = [partner.to_dict() for partner in partners]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(partners_data, f, indent=2)
    
    def scrape_partners(self, location: Optional[str] = None, 
                        max_pages: Optional[int] = None) -> List[PartnerData]:
        """
        Scrape partner data from the AppSource marketplace.
        
        Args:
            location: Filter by partner location (e.g., "United States")
            max_pages: Maximum number of pages to scrape (None for all pages)
            
        Returns:
            List of PartnerData objects
        """
        all_partners = []
        current_page = 1
        current_url = self.BASE_URL
        
        # Generate filter parameters
        params = self.apply_filters(location=location)
        
        while True:
            # Check if we've reached the maximum number of pages
            if max_pages and current_page > max_pages:
                logger.info(f"Reached maximum number of pages ({max_pages})")
                break
                
            # Fetch the current page
            html_content = self.fetch_page_content(current_url, params)
            
            # Save the HTML content
            self.save_html_content(html_content, f"partner-dir-page-{current_page}.html")
            
            # Extract partner data from the page
            partners = self.extract_partners_from_html(html_content)
            all_partners.extend(partners)
            
            logger.info(f"Extracted {len(partners)} partners from page {current_page}")
            
            # Get the URL for the next page
            next_page_url = self.get_next_page_url(html_content)
            
            if not next_page_url:
                logger.info("No more pages available")
                break
                
            # Update the current URL and page number
            current_url = next_page_url
            current_page += 1
            
            # Add delay between requests
            time.sleep(self.delay)
        
        return all_partners
