"""
HTML Structure Analyzer for Azure Partner Directory

This script fetches the HTML content from the Microsoft AppSource marketplace
and analyzes its structure to determine:
1. How to apply filters (location, capabilities, etc.)
2. How to extract partner data from the cards
3. How to handle pagination

The analysis results are saved to help implement the actual scraper.
"""
import json
import logging
import os
import time
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("analyze_html_structure.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("analyze_html_structure")

class HTMLStructureAnalyzer:
    """
    Analyzer for the HTML structure of the Azure partners directory.
    """
    
    BASE_URL = "https://appsource.microsoft.com/en-us/marketplace/partner-dir"
    
    def __init__(self, output_dir: str = "."):
        """
        Initialize the HTML Structure Analyzer.
        
        Args:
            output_dir: Directory where output files will be saved
        """
        self.output_dir = output_dir
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
    
    def analyze_filter_structure(self, html_content: str) -> Dict[str, Any]:
        """
        Analyze the filter structure of the partners directory page.
        
        Args:
            html_content: HTML content of the partners directory page
            
        Returns:
            Dictionary containing information about the filter structure
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        filter_info = {}
        
        # Look for the filter navigation section
        nav_elements = soup.select('nav[role="navigation"]')
        if nav_elements:
            logger.info(f"Found {len(nav_elements)} navigation elements")
            
            for i, nav in enumerate(nav_elements):
                filter_info[f"navigation_{i}"] = {
                    "aria_label": nav.get('aria-label', ''),
                    "class": nav.get('class', []),
                    "filter_groups": []
                }
                
                # Find filter groups within the navigation
                groups = nav.select('.ms-Nav-group')
                for j, group in enumerate(groups):
                    group_info = {
                        "expanded": "is-expanded" in group.get('class', []),
                        "items": []
                    }
                    
                    # Find filter items within the group
                    items = group.select('.ms-Nav-navItem')
                    for item in items:
                        # Get the filter name
                        name_element = item.select_one('.ms-TooltipHost span')
                        filter_name = name_element.text.strip() if name_element else ""
                        
                        # Get the filter button
                        chevron_button = item.select_one('.ms-Nav-chevronButton')
                        expanded = chevron_button.get('aria-expanded', 'false') if chevron_button else 'false'
                        
                        item_info = {
                            "name": filter_name,
                            "expanded": expanded == 'true',
                            "aria_label": chevron_button.get('aria-label', '') if chevron_button else '',
                        }
                        
                        group_info["items"].append(item_info)
                    
                    filter_info[f"navigation_{i}"]["filter_groups"].append(group_info)
        
        # Look for location filter specifically
        location_containers = soup.select('.filters-location-container')
        if location_containers:
            logger.info(f"Found {len(location_containers)} location filter containers")
            
            for i, container in enumerate(location_containers):
                filter_info[f"location_filter_{i}"] = {
                    "label_element": container.select_one('.filter-location-label').text.strip() if container.select_one('.filter-location-label') else "",
                    "edit_link": container.select_one('.filter-location-edit-link').text.strip() if container.select_one('.filter-location-edit-link') else "",
                }
        
        # Find all button elements that might be filter buttons
        filter_buttons = soup.select('button')
        filter_info["potential_filter_buttons"] = []
        
        for button in filter_buttons[:20]:  # Limit to first 20 for brevity
            button_text = button.text.strip()
            if button_text and len(button_text) > 1:
                filter_info["potential_filter_buttons"].append({
                    "text": button_text,
                    "class": button.get('class', []),
                    "aria_label": button.get('aria-label', ''),
                    "aria_expanded": button.get('aria-expanded', ''),
                })
        
        return filter_info
    
    def analyze_partner_card_structure(self, html_content: str) -> Dict[str, Any]:
        """
        Analyze the structure of partner cards on the page.
        
        Args:
            html_content: HTML content of the partners directory page
            
        Returns:
            Dictionary containing information about the partner card structure
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        card_info = {}
        
        # Look for the results container
        results_container = soup.select_one('.results-container')
        if results_container:
            logger.info("Found results container")
            card_info["results_container"] = {
                "class": results_container.get('class', []),
                "child_elements": []
            }
            
            # Look for potential card containers
            stack_elements = results_container.select('.ms-Stack')
            if stack_elements:
                logger.info(f"Found {len(stack_elements)} stack elements in results container")
                
                for i, stack in enumerate(stack_elements):
                    card_info["results_container"]["child_elements"].append({
                        "element_type": "stack",
                        "class": stack.get('class', []),
                        "css_class": stack.get('css', '')
                    })
        
        # Look for potential partner card elements with various selectors
        potential_card_selectors = [
            '.ms-List-cell', '.ms-DocumentCard', '.ms-StackItem', 
            '[role="listitem"]', '.card', '.partner-card', '.listing-item',
            '.result-item', '.ms-Grid-col', '.appCard', '.offer-card'
        ]
        
        for selector in potential_card_selectors:
            cards = soup.select(selector)
            if cards:
                logger.info(f"Found {len(cards)} potential partner cards with selector: {selector}")
                
                # Analyze the first few cards
                card_info[selector] = []
                for card in cards[:3]:  # Analyze first 3 cards
                    card_data = {
                        "tag": card.name,
                        "class": card.get('class', []),
                        "role": card.get('role', ''),
                        "links": [],
                        "images": [],
                        "headings": [],
                        "paragraphs": [],
                        "text_elements": []
                    }
                    
                    # Find links
                    for a in card.find_all('a'):
                        card_data["links"].append({
                            "text": a.text.strip(),
                            "href": a.get('href', ''),
                            "class": a.get('class', [])
                        })
                    
                    # Find images
                    for img in card.find_all('img'):
                        card_data["images"].append({
                            "alt": img.get('alt', ''),
                            "src": img.get('src', ''),
                            "class": img.get('class', [])
                        })
                    
                    # Find headings
                    for heading in card.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        card_data["headings"].append({
                            "tag": heading.name,
                            "text": heading.text.strip(),
                            "class": heading.get('class', [])
                        })
                    
                    # Find paragraphs
                    for p in card.find_all('p'):
                        card_data["paragraphs"].append({
                            "text": p.text.strip(),
                            "class": p.get('class', [])
                        })
                    
                    # Get all text elements
                    card_data["text_elements"] = [text.strip() for text in card.stripped_strings]
                    
                    card_info[selector].append(card_data)
        
        # Look for any divs with text that might be partner cards
        divs_with_text = []
        for div in soup.find_all('div'):
            text = div.text.strip()
            if text and len(text.split('\n')) >= 2:  # Has multiple lines of text
                links = div.find_all('a')
                images = div.find_all('img')
                if links and images:  # Has both links and images
                    divs_with_text.append(div)
        
        if divs_with_text:
            logger.info(f"Found {len(divs_with_text)} divs with text, links, and images")
            
            # Analyze the first few divs
            card_info["divs_with_text"] = []
            for div in divs_with_text[:3]:  # Analyze first 3 divs
                card_data = {
                    "class": div.get('class', []),
                    "id": div.get('id', ''),
                    "text_lines": [line.strip() for line in div.text.strip().split('\n')],
                    "link_count": len(div.find_all('a')),
                    "image_count": len(div.find_all('img'))
                }
                card_info["divs_with_text"].append(card_data)
        
        return card_info
    
    def analyze_pagination_structure(self, html_content: str) -> Dict[str, Any]:
        """
        Analyze the pagination structure of the partners directory page.
        
        Args:
            html_content: HTML content of the partners directory page
            
        Returns:
            Dictionary containing information about the pagination structure
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        pagination_info = {}
        
        # Look for potential pagination elements
        potential_pagination_selectors = [
            '.pagination', '.ms-Pagination', '.pager', 
            '.page-navigation', '.ms-Button--icon[title*="next"]',
            '.ms-Button--icon[aria-label*="next"]',
            '.ms-Pagination-nextPage',
            '[data-automation-key="nextPage"]'
        ]
        
        for selector in potential_pagination_selectors:
            pagination_elements = soup.select(selector)
            if pagination_elements:
                logger.info(f"Found {len(pagination_elements)} potential pagination elements with selector: {selector}")
                
                # Analyze the pagination elements
                pagination_info[selector] = []
                for element in pagination_elements[:2]:  # Analyze first 2 elements
                    element_data = {
                        "tag": element.name,
                        "class": element.get('class', []),
                        "aria_label": element.get('aria-label', ''),
                        "title": element.get('title', ''),
                        "text": element.text.strip(),
                        "links": []
                    }
                    
                    # Find links
                    for a in element.find_all('a'):
                        element_data["links"].append({
                            "text": a.text.strip(),
                            "href": a.get('href', ''),
                            "class": a.get('class', []),
                            "aria_label": a.get('aria-label', '')
                        })
                    
                    pagination_info[selector].append(element_data)
        
        # Look for buttons with "next" or "previous" in their text or attributes
        next_prev_buttons = []
        for button in soup.find_all(['button', 'a']):
            button_text = button.text.strip().lower()
            aria_label = button.get('aria-label', '').lower()
            title = button.get('title', '').lower()
            
            if ('next' in button_text or 'previous' in button_text or 
                'next' in aria_label or 'previous' in aria_label or
                'next' in title or 'previous' in title):
                next_prev_buttons.append(button)
        
        if next_prev_buttons:
            logger.info(f"Found {len(next_prev_buttons)} potential next/previous buttons")
            
            pagination_info["next_prev_buttons"] = []
            for button in next_prev_buttons:
                button_data = {
                    "tag": button.name,
                    "class": button.get('class', []),
                    "aria_label": button.get('aria-label', ''),
                    "title": button.get('title', ''),
                    "text": button.text.strip(),
                    "is_next": 'next' in button.get('aria-label', '').lower() or 'next' in button.text.strip().lower(),
                    "is_previous": 'previous' in button.get('aria-label', '').lower() or 'prev' in button.text.strip().lower()
                }
                pagination_info["next_prev_buttons"].append(button_data)
        
        return pagination_info
    
    def run_analysis(self) -> Dict[str, Any]:
        """
        Run the analysis on the partners directory page.
        
        Returns:
            Dictionary containing the analysis results
        """
        try:
            # Load the HTML content from the saved file
            html_path = os.path.join(self.output_dir, "partner-dir.html")
            logger.info(f"Loading HTML content from: {html_path}")
            
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Analyze the HTML structure
            logger.info("Analyzing filter structure...")
            filter_info = self.analyze_filter_structure(html_content)
            
            logger.info("Analyzing partner card structure...")
            card_info = self.analyze_partner_card_structure(html_content)
            
            logger.info("Analyzing pagination structure...")
            pagination_info = self.analyze_pagination_structure(html_content)
            
            # Combine all analysis results
            analysis_results = {
                "filter_structure": filter_info,
                "partner_card_structure": card_info,
                "pagination_structure": pagination_info
            }
            
            # Save the analysis results to a JSON file
            results_path = os.path.join(self.output_dir, "html_structure_analysis.json")
            logger.info(f"Saving analysis results to: {results_path}")
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_results, f, indent=2)
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error running analysis: {e}")
            raise

if __name__ == "__main__":
    analyzer = HTMLStructureAnalyzer()
    analyzer.run_analysis()
