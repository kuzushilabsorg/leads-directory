from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from firecrawl import FirecrawlApp
import time
import os
import json
import re
from datetime import datetime

api_key = 'fc-8349ece73de64dc789f42d02a45398da'
app = FirecrawlApp(api_key=api_key)

def collect_page_urls(base_url):
    """Collect all page URLs using Selenium with pagination support.
    
    Args:
        base_url (str): The base URL to start from
    
    Returns:
        list: List of all page URLs
    """
    urls = []
    driver = webdriver.Chrome()
    
    try:
        # Navigate to the URL
        driver.get(base_url)
        
        while True:
            try:
                # Add current page URL to list
                current_url = driver.current_url
                if current_url not in urls:
                    urls.append(current_url)
                    print(f"Added URL: {current_url}")
                
                # Wait for the "Next" button to appear & be clickable
                wait = WebDriverWait(driver, 20)
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Next')]")))
                
                # Click the button using JavaScript
                driver.execute_script("arguments[0].click();", next_button)
                
                # Wait for new content to load
                time.sleep(3)
                
            except (NoSuchElementException, TimeoutException):
                print("No more pages found.")
                break
    
    finally:
        driver.quit()
    
    return urls

def extract_comanies_selenium(url):
    """Extract company URLs from a webpage using Selenium.
    
    Args:
        url (str): The URL to extract data from
    
    Returns:
        list: List of dictionaries containing company URLs
    """
    driver = webdriver.Chrome()
    companies = []
    
    try:
        # Navigate to the URL
        driver.get(url)
        index = 0  # Track iteration
        
        while True:
            try:
                wait = WebDriverWait(driver, 10)
                time.sleep(5)  # Allow page to load completely
                
                # Find all tile boxes fresh in each iteration
                tile_boxes = driver.find_elements(By.XPATH, "//div[contains(@class, 'tile-container card ms-depth-8')]")
                
                if index >= len(tile_boxes):
                    break  # No more tiles on this page
                
                # Click the box to navigate to the new page
                driver.execute_script("arguments[0].click();", tile_boxes[index])
                time.sleep(3)  # Allow navigation
                
                # Get the new page URL and company name
                company_url = driver.current_url
                try:
                    company_name = driver.find_element(By.CSS_SELECTOR, ".ms-fontSize-28.ms-fontWeight-semibold.title").text.strip()
                except:
                    company_name = company_url.split('/')[-2]  # Use URL segment as fallback name
                
                print(f"Extracted: {company_name}")
                companies.append({
                    'url': company_url,
                    'name': company_name
                })
                
                # Go back to the main page
                driver.back()
                time.sleep(3)
                
                index += 1  # Move to the next element
            
            except StaleElementReferenceException:
                print(f"Stale element at index {index}. Retrying...")
                continue  # Retry the same index
            except TimeoutException:
                print("Timeout: No more elements found.")
                break
            except Exception as e:
                print(f"Error processing element {index}: {str(e)}")
                index += 1  # Try next element
                continue
                
    except Exception as e:
        print(f"Error extracting companies from {url}: {str(e)}")
        
    finally:
        driver.quit()
        
    return companies

def extract_company_details(url):
    """Extract detailed information about a company from its profile page using Selenium.
    
    Args:
        url (str): URL of the company profile page
        app (FirecrawlApp, optional): Not used in this version
    
    Returns:
        dict: Dictionary containing company details
    """
    try:
        # Setup Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode (no UI)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        driver.get(url)

        # Wait for elements to load
        wait = WebDriverWait(driver, 10)

        # Extract data
        company_details = {
            "url": url,
            "extraction_status": "success",
            "name": "",
            "description": "",
            "location": "",
            "services": [],
            "solution_category": [],
            "products": [],
            "industries": []
        }

        try:
            # Extract company name
            company_details["name"] = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".ms-fontSize-28.ms-fontWeight-semibold.title")
            )).text.strip()
        except:
            print(f"Company name not found for {url}")

        try:
            # Extract company description
            company_details["description"] = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".partner-description")
            )).text.strip()
        except:
            print(f"Company description not found for {url}")

        try:
            # Extract location
            company_details["location"] = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".ms-Dropdown-title.title-53")
            )).text.strip()
        except:
            print(f"Location not found for {url}")

        # Find all sections with class "col"
        sections = driver.find_elements(By.CSS_SELECTOR, ".col")

        for section in sections:
            try:
                heading = section.find_element(By.TAG_NAME, "h6").text.strip()
                items = [li.text.strip() for li in section.find_elements(By.CSS_SELECTOR, ".description-li")]

                # Assign data based on heading text
                if "Services" in heading:
                    company_details["services"] = items
                elif "Solution category" in heading:
                    company_details["solution_category"] = items
                elif "Products" in heading:
                    company_details["products"] = items
                elif "Industries" in heading:
                    company_details["industries"] = items

            except:
                continue  # Skip if anything goes wrong with this section

        driver.quit()
        return company_details

    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return {
            'url': url,
            'extraction_status': 'error',
            'error': str(e)
        }

def save_to_json(companies_data):
    """Save the extracted company data to a JSON file.
    
    Args:
        companies_data (list): List of dictionaries containing company information
    """
    # Create output directory if it doesn't exist
    output_dir = 'extracted_data'
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{output_dir}/companies_{timestamp}.json'
    
    # Save to JSON file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(companies_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nData saved to: {filename}")

def main():
    # Base URL to start from
    base_url = "https://main.prod.marketplacepartnerdirectory.azure.com/en/partners?filter=sort=0;pageSize=18;onlyThisCountry=true;radius=100;locationNotRequired=true"
    
    try:
        # Step 1: Collect all page URLs
        print("Step 1: Collecting page URLs...")
        page_urls = collect_page_urls(base_url)
        print(f"Found {len(page_urls)} pages\n")
        
        # Step 2: Extract basic company information from each page
        print("Step 2: Extracting company URLs...")
        company_list = []
        failed_pages = []
        
        for url in page_urls:
            try:
                print(f"Processing: {url}")
                companies = extract_comanies_selenium(url)
                if companies:
                    company_list.extend(companies)
                else:
                    failed_pages.append(url)
            except Exception as e:
                print(f"Error processing page {url}: {str(e)}")
                failed_pages.append(url)
        
        print(f"Found {len(company_list)} companies")
        if failed_pages:
            print(f"Failed to process {len(failed_pages)} pages")
        
        # Step 3: Extract detailed information for each company
        print("\nStep 3: Extracting detailed company information...")
        detailed_companies = []
        processed_count = 0
        total_companies = len(company_list)
        
        for company in company_list:
            try:
                processed_count += 1
                print(f"Processing details for: {company['name']} ({processed_count}/{total_companies})")
                company_url = company['url']
                company_details = extract_company_details(company_url)
                detailed_companies.append(company_details)  # Always append, even if extraction failed
            except Exception as e:
                print(f"Error processing company {company.get('name', 'Unknown')}: {str(e)}")
                detailed_companies.append({
                    'url': company.get('url'),
                    'name': company.get('name'),
                    'extraction_status': 'error',
                    'error': str(e)
                })
        
        # Step 4: Save the data to JSON
        successful_extractions = sum(1 for c in detailed_companies if c.get('extraction_status') == 'success')
        print(f"\nExtraction complete:")
        print(f"- Successfully extracted: {successful_extractions} companies")
        print(f"- Failed extractions: {len(detailed_companies) - successful_extractions} companies")
        save_to_json(detailed_companies)
        
    except Exception as e:
        print(f"Critical error in main execution: {str(e)}")
        # Save whatever data we have so far
        if 'detailed_companies' in locals() and detailed_companies:
            print("Saving partial data...")
            save_to_json(detailed_companies)

if __name__ == "__main__":
    main()