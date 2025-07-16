from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

# 2.1 — Configure ChromeOptions for headless browsing
chrome_opts = Options()
chrome_opts.add_argument("--disable-gpu")
chrome_opts.add_argument("--no-sandbox")
chrome_opts.add_argument("--window-size=1920,1080")
chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_opts.add_experimental_option('useAutomationExtension', False)

# 2.2 — Instantiate the WebDriver
driver = webdriver.Chrome(options=chrome_opts)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 2.3 — Build the Ads Library URL for a page ID
# Try multiple page IDs - popular brands that likely run ads in the US
page_ids_to_try = [
    ("183869772601", "Athletic Greens (AG1)"),
    ("20531316728", "Coca-Cola"),
    ("56381779049", "Nike"),
    ("114517948583012", "McDonald's"),
    ("40796308305", "Starbucks")
]

for page_id, brand_name in page_ids_to_try:
    print(f"\n=== Trying {brand_name} (ID: {page_id}) ===")
    
    ads_url = (
        "https://www.facebook.com/ads/library/"
        "?active_status=all"
        "&ad_type=all"
        "&country=US"  # Specify US country to see ads that run there
        "&media_type=all"
        "&search_type=page"
        f"&view_all_page_id={page_id}"
    )

    print(f"Navigating to: {ads_url}")

    # 2.4 — Navigate to the Ads Library page
    driver.get(ads_url)

    # Take a screenshot to see what's loaded
    driver.save_screenshot("page_loaded.png")
    print("Screenshot saved as 'page_loaded.png'")

    print("Waiting for page to load...")

    # 2.5 — Try multiple wait strategies
    try:
        # Wait for basic page structure
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("✓ Body element loaded")
        
        # Wait a bit more for dynamic content
        time.sleep(3)
        
        # Try to find various possible ad containers
        possible_selectors = [
            "[data-pagelet^='FeedUnit_']",
            "[data-testid='ad-card']",
            "[role='main']",
            "div[data-visualcompletion='ignore-dynamic']",
            "div[class*='ad']",
            "div[data-pagelet]"
        ]
        
        found_elements = []
        for selector in possible_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    found_elements.append((selector, len(elements)))
                    print(f"✓ Found {len(elements)} elements with selector: {selector}")
                else:
                    print(f"✗ No elements found with selector: {selector}")
            except Exception as e:
                print(f"✗ Error with selector {selector}: {e}")
        
        # Check page title and URL
        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # Check if we're on the right page
        if "ads/library" not in driver.current_url:
            print("⚠️  Warning: Not on ads library page!")
        
        # Try scrolling to trigger content loading
        print("Attempting to scroll and trigger content loading...")
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            print(f"Scroll attempt {i+1}")
        
        # Take another screenshot after scrolling
        driver.save_screenshot("after_scroll.png")
        print("Screenshot after scrolling saved as 'after_scroll.png'")
        
        # Look for any text content
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if len(body_text.strip()) > 0:
            print(f"Page contains {len(body_text)} characters of text")
            # Print first 500 characters to see what's there
            print("First 500 characters of page text:")
            print(body_text[:500])
        else:
            print("⚠️  Page appears to be empty!")
        
        # Check for any error messages
        error_selectors = [
            "div[role='alert']",
            ".error",
            "[data-testid='error']",
            "div:contains('error')"
        ]
        
        for selector in error_selectors:
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if error_elements:
                    print(f"⚠️  Found potential error elements: {[el.text for el in error_elements]}")
            except:
                pass
    
    except TimeoutException:
        print("✗ Timeout waiting for page elements")
    except Exception as e:
        print(f"✗ Error: {e}")

print("\nPage loading analysis complete.")
print("Check the screenshots to see what's actually displayed.")

# Keep the browser open for manual inspection
print("Browser will stay open for 30 seconds for manual inspection...")
time.sleep(30)

# When done, you can close the driver:
driver.quit()
