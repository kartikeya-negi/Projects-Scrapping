from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re

def setup_driver():
    """Setup Chrome driver with enhanced options"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    return webdriver.Chrome(options=options)

def wait_for_content_load(driver, timeout=15):
    """Wait for dynamic content to finish loading"""
    try:
        # Wait for loading messages to disappear
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'please wait')]"))
        )
    except:
        pass
    
    # Additional wait for content to stabilize
    time.sleep(3)

def extract_project_details_from_current_page(driver):
    """Extract project details with improved field targeting"""
    try:
        # Wait for page to load and dynamic content to finish
        wait_for_content_load(driver)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        def clean_text(text):
            """Clean extracted text"""
            if not text:
                return 'Not Found'
            # Remove loading messages and extra whitespace
            text = re.sub(r'please wait\.\.\.', '', text, flags=re.IGNORECASE)
            text = re.sub(r'No\s+\w+\s+Available', '', text, flags=re.IGNORECASE)
            text = ' '.join(text.split())  # Normalize whitespace
            return text.strip() if text.strip() else 'Not Found'

        def find_in_table_structure(label):
            """Find value in proper table structure"""
            # Look for label in table cells and get the corresponding value
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    for i, cell in enumerate(cells):
                        cell_text = cell.get_text(strip=True)
                        if label.lower() in cell_text.lower() and len(cell_text) < 50:  # Avoid long text blocks
                            # Get next cell in same row
                            if i + 1 < len(cells):
                                value = cells[i + 1].get_text(strip=True)
                                if value and not any(skip in value.lower() for skip in ['please wait', 'loading', 'facility of']):
                                    return clean_text(value)
            return 'Not Found'

        def find_in_form_structure(label):
            """Find value in form/div structure"""
            # Look for label followed by input or div with value
            label_element = soup.find(string=lambda text: text and label.lower() in text.lower() and len(text) < 50)
            if label_element:
                parent = label_element.parent
                # Look for input field
                input_field = parent.find_next('input')
                if input_field and input_field.get('value'):
                    return clean_text(input_field.get('value'))
                
                # Look for next sibling with text
                for sibling in parent.find_next_siblings():
                    text = sibling.get_text(strip=True)
                    if text and not any(skip in text.lower() for skip in ['please wait', 'loading', 'facility of']):
                        return clean_text(text)
            return 'Not Found'

        def get_field_value(label):
            """Try multiple strategies to get field value"""
            # Strategy 1: Table structure
            value = find_in_table_structure(label)
            if value != 'Not Found':
                return value
            
            # Strategy 2: Form structure
            value = find_in_form_structure(label)
            if value != 'Not Found':
                return value
            
            return 'Not Found'

        # Extract basic project information
        rera_regd_no = get_field_value('Rera Regd. No')
        project_name = get_field_value('Project Name')
        
        # Try to access promoter details tab
        try:
            # Look for promoter tab and click it
            promoter_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'Promoter') or contains(@href, 'promoter')]")
            driver.execute_script("arguments[0].click();", promoter_tab)
            wait_for_content_load(driver)
            # Re-parse after clicking tab
            soup = BeautifulSoup(driver.page_source, 'html.parser')
        except Exception as e:
            print(f"Could not access promoter tab: {e}")

        # Extract promoter information
        promoter_name = get_field_value('Company Name')
        if promoter_name == 'Not Found':
            promoter_name = get_field_value('Promoter Name')
        
        promoter_address = get_field_value('Registered Office Address')
        if promoter_address == 'Not Found':
            promoter_address = get_field_value('Office Address')
        
        gst_no = get_field_value('GST No')
        if gst_no == 'Not Found':
            gst_no = get_field_value('GSTIN')

        return {
            'Rera Regd. No': rera_regd_no,
            'Project Name': project_name,
            'Promoter Name': promoter_name,
            'Address of the Promoter': promoter_address,
            'GST No.': gst_no
        }
        
    except Exception as e:
        print(f"Error extracting details: {e}")
        return None

def scrape_ongoing_projects():
    """Main scraping function"""
    driver = setup_driver()
    
    try:
        print("Loading main page...")
        driver.get('https://rera.odisha.gov.in/projects/project-list')
        
        # Wait for page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'View Details')]"))
        )
        
        project_details = []
        
        for i in range(6):
            try:
                print(f"Processing project {i+1}...")
                
                # Get fresh list of View Details buttons
                view_details_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'View Details')]")
                
                if i >= len(view_details_buttons):
                    print(f"Only {len(view_details_buttons)} projects available")
                    break
                
                # Click the button
                button = view_details_buttons[i]
                driver.execute_script("arguments[0].click();", button)
                
                # Wait for detail page and extract
                time.sleep(5)  # Give more time for page to load
                details = extract_project_details_from_current_page(driver)
                
                if details:
                    project_details.append(details)
                    print(f"Extracted: {details['Project Name']} - {details['Rera Regd. No']}")
                
                # Go back to main page
                driver.back()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'View Details')]"))
                )
                time.sleep(2)
                
            except Exception as e:
                print(f"Error processing project {i+1}: {e}")
                # Try to return to main page
                try:
                    driver.get('https://rera.odisha.gov.in/projects/project-list')
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'View Details')]"))
                    )
                except:
                    pass
                continue
        
        return project_details
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        return None
    finally:
        driver.quit()

if __name__ == "__main__":
    projects = scrape_ongoing_projects()
    
    if projects:
        print(f"\nSuccessfully scraped {len(projects)} projects:")
        print("=" * 50)
        for idx, project in enumerate(projects, 1):
            print(f"Project {idx}:")
            for k, v in project.items():
                print(f"  {k}: {v}")
            print("-" * 40)
    else:
        print("Scraping failed.")
