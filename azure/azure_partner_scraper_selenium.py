"""
Azure Partner Scraper using Selenium

This module provides functionality to scrape partner information from the Microsoft AppSource
marketplace using Selenium to handle JavaScript-rendered content. It handles filtering,
pagination, and data extraction.

Classes:
    AzurePartnerScraperSelenium: Main class for scraping partner data from AppSource using Selenium
    PartnerData: Data class for storing partner information
"""
import json
import logging
import os
import time
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("azure_partner_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("azure_partner_scraper_selenium")

@dataclass
class PartnerData:
    """Data class for storing partner information extracted from AppSource."""
    name: str
    url: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    location: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the partner data to a dictionary."""
        return asdict(self)


class AzurePartnerScraperSelenium:
    """
    Scraper for Azure partners from Microsoft AppSource marketplace using Selenium.
    
    This class handles:
    - Fetching HTML content from the partners directory
    - Applying filters (location, capabilities, etc.)
    - Extracting partner data from the page
    - Handling pagination to process all available partners
    """
    
    BASE_URL = "https://appsource.microsoft.com/en-us/marketplace/partner-dir"
    
    def __init__(self, output_dir: str = ".", delay_between_actions: float = 1.0, 
                 headless: bool = True, chrome_driver_path: Optional[str] = None):
        """
        Initialize the Azure Partner Scraper with Selenium.
        
        Args:
            output_dir: Directory where output files will be saved
            delay_between_actions: Time to wait between browser actions (in seconds)
            headless: Whether to run the browser in headless mode
            chrome_driver_path: Path to the Chrome driver executable (optional)
        """
        self.output_dir = output_dir
        self.delay = delay_between_actions
        self.headless = headless
        self.chrome_driver_path = chrome_driver_path
        self.driver = None
        
    def _initialize_driver(self):
        """Initialize the Selenium WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        if self.chrome_driver_path:
            service = Service(executable_path=self.chrome_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Use webdriver_manager to automatically download and manage the ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
        self.driver.implicitly_wait(10)
        
    def _close_driver(self):
        """Close the Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            
    def fetch_page_content(self, url: str) -> str:
        """
        Fetch the HTML content of a page using Selenium.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            HTML content of the page
        """
        self.driver.get(url)
        
        # Wait for the body element to be present
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Wait for any loading indicators to disappear
        try:
            loading_indicators = [
                ".loading-indicator", 
                ".spinner", 
                ".loading", 
                "[role='progressbar']",
                ".ms-Spinner",
                ".ms-Shimmer-container"
            ]
            for indicator in loading_indicators:
                try:
                    WebDriverWait(self.driver, 10).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
                    )
                except TimeoutException:
                    # If the indicator is not found or doesn't disappear, continue
                    pass
        except Exception as e:
            logger.warning(f"Error waiting for loading indicators: {e}")
        
        # Look for specific content elements that indicate the page has loaded
        try:
            content_elements = [
                ".partner-card", 
                ".listing-item", 
                ".result-item",
                "[role='listitem']",
                ".ms-List-cell",
                ".ms-DocumentCard",
                "div.card",
                ".appCard",
                ".offer-card",
                ".ms-Grid-col",
                "div[class*='card']",
                "div[class*='item']"
            ]
            
            # Wait for at least one content element to be present
            for element in content_elements:
                try:
                    WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, element))
                    )
                    logger.info(f"Found content element: {element}")
                    break
                except TimeoutException:
                    # If the element is not found, continue to the next one
                    continue
        except Exception as e:
            logger.warning(f"Error waiting for content elements: {e}")
        
        # Scroll down to trigger lazy loading
        try:
            # Scroll down multiple times with pauses to ensure all content loads
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Error scrolling page: {e}")
        
        # Additional wait time to ensure all JavaScript has executed
        time.sleep(3)
        
        return self.driver.page_source
    
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
    
    def apply_filter(self, filter_type: str, filter_value: str) -> None:
        """
        Apply a filter to the partners directory page.
        
        Args:
            filter_type: Type of filter (e.g., "location", "capability", "industry")
            filter_value: Value to filter by
        """
        logger.info(f"Applying filter: {filter_type} = {filter_value}")
        
        try:
            # Wait for the page to load completely
            time.sleep(3)
            
            # Special handling for location filter
            if filter_type.lower() == "location":
                try:
                    # Look for the location filter container
                    location_container = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".filters-location-container"))
                    )
                    
                    # Find and click the "Select location" link
                    location_edit_link = location_container.find_element(By.CSS_SELECTOR, ".filter-location-edit-link")
                    location_edit_link.click()
                    logger.info("Clicked 'Select location' link")
                    time.sleep(2)
                    
                    # Wait for the location dialog to appear
                    location_dialog = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".ms-Dialog, .ms-Panel, [role='dialog']"))
                    )
                    
                    # Try to find the search box in the dialog
                    search_boxes = location_dialog.find_elements(By.CSS_SELECTOR, 
                        "input[type='text'], .ms-SearchBox-field, [role='searchbox']")
                    
                    if search_boxes:
                        search_box = search_boxes[0]
                        search_box.clear()
                        search_box.send_keys(filter_value)
                        search_box.send_keys(Keys.ENTER)
                        logger.info(f"Entered location search: {filter_value}")
                        time.sleep(2)
                    
                    # Look for matching location options
                    location_options = location_dialog.find_elements(By.XPATH, 
                        f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{filter_value.lower()}')]")
                    
                    if location_options:
                        for option in location_options:
                            if option.is_displayed() and option.is_enabled():
                                option.click()
                                logger.info(f"Selected location: {option.text}")
                                time.sleep(2)
                                
                                # Look for Apply/OK button
                                apply_buttons = location_dialog.find_elements(By.CSS_SELECTOR, 
                                    "button.ms-Button--primary, [aria-label='Apply'], [aria-label='OK']")
                                
                                if apply_buttons:
                                    apply_buttons[0].click()
                                    logger.info("Clicked Apply button for location filter")
                                    time.sleep(3)
                                    return
                    
                    # If we couldn't find or select a location, try to close the dialog
                    close_buttons = location_dialog.find_elements(By.CSS_SELECTOR, 
                        "button.ms-Dialog-button--close, .ms-Panel-closeButton, [aria-label='Close']")
                    
                    if close_buttons:
                        close_buttons[0].click()
                        logger.info("Closed location dialog without selecting")
                        time.sleep(1)
                
                except Exception as e:
                    logger.warning(f"Error applying location filter: {e}")
                    # Continue with the general filter approach
            
            # For other filter types, use the navigation filter structure
            # Look for filter in the navigation menu
            nav_elements = self.driver.find_elements(By.CSS_SELECTOR, "nav[role='navigation']")
            
            if nav_elements:
                nav = nav_elements[0]
                
                # Find all filter groups
                groups = nav.find_elements(By.CSS_SELECTOR, ".ms-Nav-group")
                
                for group in groups:
                    # Find filter items within the group
                    items = group.find_elements(By.CSS_SELECTOR, ".ms-Nav-navItem")
                    
                    for item in items:
                        # Get the filter name
                        name_element = item.find_element(By.CSS_SELECTOR, ".ms-TooltipHost span") if item.find_elements(By.CSS_SELECTOR, ".ms-TooltipHost span") else None
                        
                        if name_element:
                            filter_name = name_element.text.strip()
                            
                            # Check if this is the filter we're looking for
                            if (filter_type.lower() in filter_name.lower() or 
                                self._similar_text(filter_type, filter_name)):
                                
                                # Get the chevron button to expand the filter
                                chevron_button = item.find_element(By.CSS_SELECTOR, ".ms-Nav-chevronButton") if item.find_elements(By.CSS_SELECTOR, ".ms-Nav-chevronButton") else None
                                
                                if chevron_button:
                                    # Check if already expanded
                                    expanded = chevron_button.get_attribute('aria-expanded')
                                    
                                    if expanded != 'true':
                                        # Click to expand
                                        chevron_button.click()
                                        logger.info(f"Expanded filter: {filter_name}")
                                        time.sleep(2)
                                    
                                    # Now look for the filter value in the expanded section
                                    # First, find the parent composite link
                                    composite_link = item.find_element(By.CSS_SELECTOR, ".ms-Nav-compositeLink")
                                    
                                    # Find the expanded content - it should be a sibling or child of the composite link
                                    expanded_content = None
                                    
                                    # Try to find expanded content as a sibling
                                    parent = composite_link.find_element(By.XPATH, "./..")
                                    expanded_elements = parent.find_elements(By.CSS_SELECTOR, 
                                        ".ms-Nav-navItems, .ms-Nav-group, [role='group']")
                                    
                                    if expanded_elements:
                                        expanded_content = expanded_elements[0]
                                    
                                    if expanded_content:
                                        # Look for checkboxes or links with the filter value
                                        filter_options = expanded_content.find_elements(By.XPATH, 
                                            f".//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{filter_value.lower()}')]")
                                        
                                        if filter_options:
                                            for option in filter_options:
                                                if option.is_displayed():
                                                    # Scroll to the option
                                                    self.driver.execute_script("arguments[0].scrollIntoView();", option)
                                                    time.sleep(1)
                                                    
                                                    # Click the option
                                                    option.click()
                                                    logger.info(f"Selected filter value: {option.text}")
                                                    time.sleep(3)
                                                    return
                                    
                                    # If we couldn't find or select a value, collapse the filter
                                    if expanded == 'false':
                                        chevron_button.click()
                                        logger.info(f"Collapsed filter: {filter_name}")
                                        time.sleep(1)
            
            # If we couldn't find the filter using the navigation structure, fall back to the previous approach
            # First, try to find filter buttons by their text content
            filter_buttons = self.driver.find_elements(By.XPATH, 
                f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{filter_type.lower()}')]")
            
            # If no buttons found by text, try common filter button selectors
            if not filter_buttons:
                filter_selectors = [
                    "button.filter-button", 
                    ".filter-dropdown",
                    ".ms-Dropdown",
                    ".ms-ComboBox",
                    ".ms-Dropdown-container",
                    ".ms-Dropdown-title",
                    ".ms-Button",
                    "[role='combobox']",
                    "[aria-haspopup='listbox']",
                    f"[data-automation-id*='{filter_type}']",
                    f"[id*='{filter_type}']",
                    f"[aria-label*='{filter_type}']"
                ]
                
                for selector in filter_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Check if the element text contains the filter type
                        element_text = element.text.lower()
                        if filter_type.lower() in element_text or self._similar_text(filter_type, element_text):
                            filter_buttons.append(element)
                    
                    if filter_buttons:
                        break
            
            # If still no filter buttons found, try to find any clickable elements that might be filters
            if not filter_buttons:
                logger.info(f"Searching for any potential filter elements for {filter_type}")
                
                # Look for elements with filter-related classes or attributes
                potential_filters = self.driver.find_elements(By.CSS_SELECTOR, 
                    "[class*='filter'], [class*='dropdown'], [class*='menu'], [class*='select'], button, [role='button']")
                
                for element in potential_filters:
                    try:
                        element_text = element.text.lower()
                        element_html = element.get_attribute('outerHTML').lower()
                        
                        # Check if element might be related to our filter type
                        if (filter_type.lower() in element_text or 
                            filter_type.lower() in element_html or
                            self._similar_text(filter_type, element_text)):
                            
                            filter_buttons.append(element)
                    except:
                        continue
            
            if not filter_buttons:
                logger.warning(f"Could not find filter '{filter_type}' with value '{filter_value}'")
                return
            
            # Try to click each potential filter button until we find one that works
            filter_applied = False
            for button in filter_buttons:
                try:
                    # Scroll to the button to make it visible
                    self.driver.execute_script("arguments[0].scrollIntoView();", button)
                    time.sleep(1)
                    
                    # Click the filter button
                    button.click()
                    logger.info(f"Clicked filter button for {filter_type}")
                    time.sleep(2)
                    
                    # Now look for the filter value in the dropdown or list
                    filter_options = []
                    
                    # Try different selectors for filter options
                    option_selectors = [
                        ".ms-Dropdown-item", 
                        ".ms-ComboBox-option",
                        ".dropdown-item",
                        ".filter-option",
                        "li",
                        "[role='option']",
                        "[role='menuitem']",
                        "[class*='option']",
                        "[class*='item']"
                    ]
                    
                    for selector in option_selectors:
                        options = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if options:
                            filter_options = options
                            break
                    
                    # If no options found with CSS selectors, try XPath to find any elements with the filter value
                    if not filter_options:
                        filter_options = self.driver.find_elements(By.XPATH, 
                            f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{filter_value.lower()}')]")
                    
                    # Try to click the option with the matching filter value
                    for option in filter_options:
                        option_text = option.text.strip().lower()
                        if (filter_value.lower() in option_text or 
                            self._similar_text(filter_value, option_text)):
                            
                            # Scroll to the option to make it visible
                            self.driver.execute_script("arguments[0].scrollIntoView();", option)
                            time.sleep(1)
                            
                            # Click the option
                            option.click()
                            logger.info(f"Selected filter value: {filter_value}")
                            filter_applied = True
                            break
                    
                    if filter_applied:
                        # Wait for the page to update after applying the filter
                        time.sleep(3)
                        break
                    else:
                        # If we couldn't find the value, click the button again to close the dropdown
                        button.click()
                        time.sleep(1)
                
                except Exception as e:
                    logger.warning(f"Error applying filter {filter_type}={filter_value}: {e}")
                    # Try the next button
                    continue
            
            if not filter_applied:
                logger.warning(f"Could not apply filter {filter_type}={filter_value}")
        
        except Exception as e:
            logger.error(f"Error applying filter {filter_type}={filter_value}: {e}")
    
    def _similar_text(self, text1: str, text2: str) -> bool:
        """
        Check if two texts are similar (for fuzzy matching of filter names).
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            True if texts are similar, False otherwise
        """
        # Convert to lowercase and remove common words
        text1 = text1.lower()
        text2 = text2.lower()
        
        # Check for common variations of filter types
        if text1 == "location":
            return any(word in text2 for word in ["location", "country", "region", "geography", "area"])
        elif text1 == "capability":
            return any(word in text2 for word in ["capability", "service", "skill", "expertise", "competency"])
        elif text1 == "industry":
            return any(word in text2 for word in ["industry", "sector", "vertical", "market"])
        
        # Default case - check if one is contained in the other
        return text1 in text2 or text2 in text1
    
    def extract_partners_from_page(self) -> List[PartnerData]:
        """
        Extract partner data from the current page.
        
        Returns:
            List of PartnerData objects
        """
        partners = []
        
        try:
            # Wait for the page to load completely
            time.sleep(3)
            
            # First, check if we have partner cards with role="listitem"
            partner_cards = self.driver.find_elements(By.CSS_SELECTOR, "[role='listitem']")
            
            # If no cards found with role="listitem", try other selectors
            if not partner_cards:
                # Try different selectors for partner cards based on HTML analysis
                selectors = [
                    ".card", 
                    ".tile-container",
                    ".partner-card", 
                    ".listing-item", 
                    ".result-item",
                    ".ms-List-cell", 
                    ".ms-DocumentCard", 
                    ".ms-StackItem"
                ]
                
                for selector in selectors:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if cards:
                        partner_cards = cards
                        logger.info(f"Found {len(cards)} partner cards with selector: {selector}")
                        break
            
            # If still no cards found, try to find any div elements that might be partner cards
            if not partner_cards:
                logger.info("Searching for any potential partner card elements")
                
                # Look for divs with multiple text elements and links
                divs = self.driver.find_elements(By.TAG_NAME, "div")
                
                for div in divs:
                    try:
                        # Check if div has links and text content
                        links = div.find_elements(By.TAG_NAME, "a")
                        paragraphs = div.find_elements(By.TAG_NAME, "p")
                        
                        if links and paragraphs and len(paragraphs) >= 2:
                            # This might be a partner card
                            partner_cards.append(div)
                    except:
                        continue
                
                if partner_cards:
                    logger.info(f"Found {len(partner_cards)} potential partner cards by analyzing div elements")
            
            if not partner_cards:
                logger.warning("Could not find any partner cards on the page")
                return []
            
            # Set a timeout for processing all cards to prevent hanging
            start_time = time.time()
            max_processing_time = 60  # Maximum time in seconds to spend processing cards
            
            logger.info(f"Processing {len(partner_cards)} partner cards")
            
            # Process each partner card
            for i, card in enumerate(partner_cards):
                # Check if we've exceeded the maximum processing time
                if time.time() - start_time > max_processing_time:
                    logger.warning(f"Reached maximum processing time after processing {i} cards")
                    break
                
                try:
                    # Extract partner data from the card
                    partner = PartnerData(name="", url="")
                    
                    # Extract partner name
                    name_elements = card.find_elements(By.CSS_SELECTOR, 
                        "h1, h2, h3, h4, h5, h6, .partner-name, .title, [class*='title'], [class*='name'], strong, b")
                    
                    if name_elements:
                        partner.name = name_elements[0].text.strip()
                    else:
                        # Try to find any text that might be a name
                        paragraphs = card.find_elements(By.TAG_NAME, "p")
                        if paragraphs:
                            partner.name = paragraphs[0].text.strip()
                    
                    # Skip if no name found
                    if not partner.name:
                        continue
                    
                    # Extract partner URL
                    link_elements = card.find_elements(By.TAG_NAME, "a")
                    
                    for link in link_elements:
                        href = link.get_attribute("href")
                        if href and "appsource.microsoft.com" in href and "/product/" in href:
                            partner.url = href
                            break
                    
                    # If no product URL found, use any URL
                    if not partner.url and link_elements:
                        partner.url = link_elements[0].get_attribute("href") or ""
                    
                    # Extract partner location
                    location_elements = card.find_elements(By.XPATH, 
                        ".//*[contains(text(), ',')]")  # Locations often have commas (City, Country)
                    
                    if location_elements:
                        for element in location_elements:
                            text = element.text.strip()
                            # Check if this looks like a location (contains a comma and not too long)
                            if "," in text and len(text) < 100:
                                partner.location = text
                                break
                    
                    # Extract partner description
                    description_elements = card.find_elements(By.CSS_SELECTOR, 
                        ".description, [class*='description'], [class*='overview'], p")
                    
                    if description_elements:
                        # Find the longest paragraph that's likely to be a description
                        descriptions = []
                        for element in description_elements:
                            text = element.text.strip()
                            if text and len(text) > 20 and "..." in text:  # Descriptions often end with ellipsis
                                descriptions.append(text)
                            elif text and len(text) > 50:  # Or they're just longer text
                                descriptions.append(text)
                        
                        if descriptions:
                            # Use the longest description
                            partner.description = max(descriptions, key=len)
                    
                    # Extract partner capabilities
                    # Look for lists of technologies or capabilities
                    capability_elements = card.find_elements(By.CSS_SELECTOR, 
                        ".tag, [class*='tag'], [class*='pill'], [class*='chip'], [class*='badge']")
                    
                    if capability_elements:
                        for element in capability_elements:
                            text = element.text.strip()
                            if text and text not in ["Contact me", "Next", "Previous"]:
                                partner.capabilities.append(text)
                    
                    # If no capabilities found with specific selectors, look for any short text elements
                    if not partner.capabilities:
                        # Get all text elements
                        all_text_elements = []
                        for element in card.find_elements(By.XPATH, ".//*"):
                            try:
                                text = element.text.strip()
                                if text and 3 <= len(text) <= 30 and text not in ["Contact me", "Next", "Previous"]:
                                    all_text_elements.append(text)
                            except:
                                continue
                        
                        # Filter out elements that are likely to be capabilities
                        known_capabilities = [
                            "Azure", "Office 365", "Dynamics 365", "Microsoft 365", "Power BI", 
                            "SharePoint", "Teams", "Exchange", "SQL", "Windows", "Developer Tools"
                        ]
                        
                        for text in all_text_elements:
                            if text in known_capabilities or any(cap in text for cap in known_capabilities):
                                partner.capabilities.append(text)
                    
                    # Add the partner to the list if we have at least a name
                    if partner.name:
                        partners.append(partner)
                        logger.info(f"Extracted partner: {partner.name}")
                
                except Exception as e:
                    logger.warning(f"Error extracting partner data from card {i}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(partners)} partners from the page")
            
        except Exception as e:
            logger.error(f"Error extracting partners from page: {e}")
        
        return partners
    
    def go_to_next_page(self) -> bool:
        """
        Navigate to the next page of partners.
        
        Returns:
            True if successfully navigated to the next page, False otherwise
        """
        logger.info("Attempting to navigate to the next page")
        
        try:
            # Wait for the page to load completely
            time.sleep(3)
            
            # Look for next button with icon character (from HTML analysis)
            next_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), '\ue76c')]")
            
            if not next_buttons:
                # Try to find next button by aria-label
                next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "[aria-label*='Next'], [aria-label*='next'], [title*='Next'], [title*='next']")
            
            if not next_buttons:
                # Try to find by common next button classes
                next_selectors = [
                    ".ms-Button--icon[title*='next']",
                    ".ms-Button--icon[aria-label*='next']",
                    ".ms-Pagination-nextPage",
                    "[data-automation-key='nextPage']",
                    ".next-page",
                    ".pagination-next",
                    "[aria-label='Next page']"
                ]
                
                for selector in next_selectors:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        next_buttons = buttons
                        break
            
            if not next_buttons:
                # As a last resort, look for any button with next-like text
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for button in all_buttons:
                    try:
                        button_text = button.text.lower()
                        if "next" in button_text or ">" in button_text or "→" in button_text:
                            next_buttons = [button]
                            break
                    except:
                        continue
            
            if not next_buttons:
                logger.info("No next page button found - reached the last page")
                return False
            
            # Check if the next button is enabled
            next_button = next_buttons[0]
            is_disabled = next_button.get_attribute("disabled") == "true" or "disabled" in next_button.get_attribute("class") or not next_button.is_enabled()
            
            if is_disabled:
                logger.info("Next page button is disabled - reached the last page")
                return False
            
            # Scroll to the button to make it visible
            self.driver.execute_script("arguments[0].scrollIntoView();", next_button)
            time.sleep(1)
            
            # Click the next button
            next_button.click()
            logger.info("Clicked next page button")
            
            # Wait for the page to load
            time.sleep(5)
            
            # Verify that we've navigated to a new page
            # One way is to check if the URL has changed, but this might not be reliable
            # Another way is to check if the page content has changed
            
            # For now, we'll assume the navigation was successful if we didn't get an error
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False
    
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
                        capabilities: Optional[List[str]] = None,
                        industries: Optional[List[str]] = None,
                        max_pages: Optional[int] = None) -> List[PartnerData]:
        """
        Scrape partner data from the AppSource marketplace.
        
        Args:
            location: Filter by partner location (e.g., "United States")
            capabilities: List of capabilities to filter by
            industries: List of industries to filter by
            max_pages: Maximum number of pages to scrape (None for all pages)
            
        Returns:
            List of PartnerData objects
        """
        all_partners = []
        current_page = 1
        
        try:
            # Initialize the driver if not already initialized
            if not self.driver:
                self._initialize_driver()
            
            # Navigate to the base URL
            self.driver.get(self.BASE_URL)
            
            # Wait for the page to load
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for any loading indicators to disappear
            time.sleep(5)
            
            # Apply filters if specified
            if location:
                self.apply_filter("location", location)
                # Wait for the filter to be applied and the page to update
                time.sleep(5)
            
            if capabilities:
                for capability in capabilities:
                    self.apply_filter("capability", capability)
                    time.sleep(3)
            
            if industries:
                for industry in industries:
                    self.apply_filter("industry", industry)
                    time.sleep(3)
            
            # Save the initial HTML content
            html_content = self.driver.page_source
            self.save_html_content(html_content, "partner-dir.html")
            
            while True:
                # Check if we've reached the maximum number of pages
                if max_pages and current_page > max_pages:
                    logger.info(f"Reached maximum number of pages ({max_pages})")
                    break
                
                logger.info(f"Processing page {current_page}")
                
                # Extract partner data from the current page
                partners = self.extract_partners_from_page()
                all_partners.extend(partners)
                
                logger.info(f"Extracted {len(partners)} partners from page {current_page}")
                
                # Save the current page HTML
                html_content = self.driver.page_source
                self.save_html_content(html_content, f"partner-dir-page-{current_page}.html")
                
                # Go to the next page
                if not self.go_to_next_page():
                    logger.info("No more pages available")
                    break
                
                current_page += 1
                time.sleep(3)  # Wait between page navigations
                
        except Exception as e:
            logger.error(f"Error scraping partners: {e}")
            
        finally:
            # Close the driver
            self._close_driver()
        
        return all_partners
