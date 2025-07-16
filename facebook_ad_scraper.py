from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import csv
import pandas as pd
from datetime import datetime
import os
import re
from urllib.parse import urljoin
import requests
from config import COMPETITORS, TARGET_COUNTRIES, SCRAPING_CONFIG, EXPORT_CONFIG, PERFORMANCE_WEIGHTS

class FacebookAdLibraryScraper:
    def __init__(self, headless=None, screenshot_dir=None):
        """
        Initialize the Facebook Ad Library scraper
        
        Args:
            headless (bool): Run browser in headless mode (defaults to config value)
            screenshot_dir (str): Directory to save screenshots for debugging
        """
        # Load configuration from config.py
        self.competitors = COMPETITORS
        self.target_countries = TARGET_COUNTRIES
        
        # Use config values with overrides
        if headless is None:
            headless = SCRAPING_CONFIG.get("headless", True)
        if screenshot_dir is None:
            screenshot_dir = "screenshots"
        
        self.screenshot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # Setup Chrome options
        self.chrome_opts = Options()
        if headless:
            self.chrome_opts.add_argument("--headless")
        self.chrome_opts.add_argument("--disable-gpu")
        self.chrome_opts.add_argument("--no-sandbox")
        self.chrome_opts.add_argument("--window-size=1920,1080")
        self.chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_opts.add_experimental_option('useAutomationExtension', False)
        
        self.driver = None
        self.all_ads_data = []
        
    def start_driver(self):
        """Initialize the Chrome WebDriver"""
        self.driver = webdriver.Chrome(options=self.chrome_opts)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def stop_driver(self):
        """Close the Chrome WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def build_ads_url(self, page_id, country="ALL"):
        """
        Build Facebook Ads Library URL for a specific page and country
        Uses the exact URL format as provided by the user
        
        Args:
            page_id (str): Facebook page ID
            country (str): Two-letter country code or "ALL" for global search
            
        Returns:
            str: Complete Ads Library URL
        """
        return (
            "https://www.facebook.com/ads/library/"
            "?active_status=active"
            "&ad_type=all"
            f"&country={country}"
            "&is_targeted_country=false"
            "&media_type=all"
            "&search_type=page"
            "&source=nav-header"
            f"&view_all_page_id={page_id}"
        )
    
    def wait_for_page_load(self, timeout=None):
        """Wait for the page to load and return True if successful"""
        if timeout is None:
            timeout = SCRAPING_CONFIG.get("wait_timeout", 15)
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Additional wait for dynamic content
            return True
        except TimeoutException:
            return False
    
    def check_for_ads(self):
        """Check if ads are present on the current page"""
        # Check for no-results messages first
        no_results_texts = [
            "No results found",
            "couldn't find any ads",
            "No ads to show",
            "There are no ads to show"
        ]
        
        page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
        for text in no_results_texts:
            if text.lower() in page_text:
                return False, f"No ads found: {text}"

        # Look for ad containers using updated selectors based on DOM analysis
        # Facebook uses heavily obfuscated CSS classes, so we need to be more flexible
        ad_selectors = [
            # Look for divs containing external links (which ads typically have)
            "div:has(a[href*='l.facebook.com/l.php'])",  # External link redirects
            "a[href*='l.facebook.com/l.php']",  # Direct external links
            # Look for common Facebook container patterns
            "div[class*='x78zum5']",  # Common FB container class
            "div[class*='xdt5ytf']",  # Another common FB class
            # Look for elements with the brand name
            "*:contains('AG1')",  # Elements containing AG1
            "*:contains('Athletic Greens')",  # Elements containing Athletic Greens
        ]
        
        total_ads = 0
        found_external_links = 0
        
        # Check for external links (most reliable indicator of ads)
        try:
            external_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='l.facebook.com/l.php']")
            found_external_links = len(external_links)
            print(f"   Found {found_external_links} external links")
        except Exception as e:
            print(f"   Error checking external links: {e}")
        
        # Check for AG1/Athletic Greens mentions
        try:
            ag1_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'AG1') or contains(text(), 'Athletic Greens')]")
            ag1_count = len(ag1_elements)
            print(f"   Found {ag1_count} AG1/Athletic Greens mentions")
            total_ads += ag1_count
        except Exception as e:
            print(f"   Error checking AG1 mentions: {e}")
        
        # Check for common container patterns
        for selector in ad_selectors[:4]:  # Only test the CSS selectors
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                element_count = len(elements)
                if element_count > 0:
                    print(f"   {selector}: {element_count} elements")
                    # Don't add all container elements, just use as indicator
                    if 'l.facebook.com' in selector:
                        total_ads += element_count
            except Exception as e:
                continue

        # Use external links as primary indicator
        if found_external_links > 0:
            return True, f"Found {found_external_links} ads with external links"
        elif total_ads > 0:
            return True, f"Found {total_ads} potential ad elements"
        else:
            return False, "No ad elements found"
    
    def extract_ad_data(self):
        """Extract detailed ad data from the current page"""
        ads_data = []
        
        # Scroll to load more ads
        self.scroll_to_load_content()
        
        # Find ads by looking for external links (most reliable approach)
        ad_elements = []
        try:
            # Find all external links which indicate ads
            external_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='l.facebook.com/l.php']")
            print(f"Found {len(external_links)} external links")
            
            # Get parent containers of these links as ad elements
            for link in external_links:
                try:
                    # Try to find a good parent container
                    # Look for divs that are 2-4 levels up from the link
                    parent = link
                    for level in range(4):  # Go up 4 levels max
                        parent = parent.find_element(By.XPATH, "..")
                        if parent.tag_name == 'div':
                            # Check if this div seems like an ad container
                            parent_class = parent.get_attribute('class') or ''
                            if ('x78zum5' in parent_class or 'xdt5ytf' in parent_class or 
                                len(parent_class.split()) > 5):  # Lots of classes = likely container
                                ad_elements.append(parent)
                                break
                except Exception as e:
                    continue
                    
            # Remove duplicates by comparing element locations
            unique_elements = []
            for element in ad_elements:
                try:
                    location = element.location
                    size = element.size
                    element_signature = f"{location['x']},{location['y']},{size['width']},{size['height']}"
                    
                    # Check if we already have an element at this location
                    is_duplicate = False
                    for existing in unique_elements:
                        try:
                            existing_location = existing.location
                            existing_size = existing.size
                            existing_signature = f"{existing_location['x']},{existing_location['y']},{existing_size['width']},{existing_size['height']}"
                            if element_signature == existing_signature:
                                is_duplicate = True
                                break
                        except:
                            continue
                    
                    if not is_duplicate:
                        unique_elements.append(element)
                except:
                    continue
            
            ad_elements = unique_elements
            
        except Exception as e:
            print(f"Error finding external links: {e}")
            # Fallback to broader container search
            ad_container_selectors = [
                "div[class*='x78zum5']",
                "div[class*='xdt5ytf']"
            ]
            
            for selector in ad_container_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    # Filter for elements that likely contain ads
                    for element in elements:
                        if 'AG1' in element.text or 'Athletic Greens' in element.text:
                            ad_elements.append(element)
                except:
                    continue
        
        print(f"Found {len(ad_elements)} unique ad containers to process")
        
        max_ads = SCRAPING_CONFIG.get("max_ads_per_country", 50)
        for i, ad_element in enumerate(ad_elements[:max_ads]):  # Limit ads per config
            try:
                ad_data = self.extract_single_ad_data(ad_element, i)
                if ad_data:
                    ads_data.append(ad_data)
            except Exception as e:
                print(f"Error extracting ad {i}: {e}")
                continue
        
        return ads_data
    
    def extract_single_ad_data(self, ad_element, index):
        """Extract data from a single ad element"""
        ad_data = {
            'index': index,
            'timestamp': datetime.now().isoformat(),
            'text_content': '',
            'media_urls': [],
            'engagement_metrics': {},
            'ad_details': {},
            'cta_button': '',
            'link_url': ''
        }
        
        try:
            # Extract text content
            ad_data['text_content'] = ad_element.text.strip()
            
            # Look for images and videos
            media_elements = ad_element.find_elements(By.CSS_SELECTOR, "img, video")
            for media in media_elements:
                src = media.get_attribute('src')
                if src and src.startswith('http'):
                    ad_data['media_urls'].append(src)
            
            # Look for engagement metrics (likes, shares, comments)
            engagement_selectors = [
                "[aria-label*='like']",
                "[aria-label*='share']", 
                "[aria-label*='comment']",
                "span[data-testid*='count']"
            ]
            
            for selector in engagement_selectors:
                try:
                    elements = ad_element.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.get_attribute('aria-label') or elem.text
                        if text and any(word in text.lower() for word in ['like', 'share', 'comment']):
                            ad_data['engagement_metrics'][selector] = text
                except:
                    continue
            
            # Look for CTA buttons
            cta_selectors = [
                "a[role='button']",
                "button",
                "[data-testid*='cta']"
            ]
            
            for selector in cta_selectors:
                try:
                    cta_elements = ad_element.find_elements(By.CSS_SELECTOR, selector)
                    for cta in cta_elements:
                        if cta.text.strip():
                            ad_data['cta_button'] = cta.text.strip()
                            ad_data['link_url'] = cta.get_attribute('href') or ''
                            break
                except:
                    continue
            
            # Extract ad library specific details
            self.extract_ad_library_details(ad_element, ad_data)
            
        except Exception as e:
            print(f"Error in extract_single_ad_data: {e}")
        
        return ad_data if ad_data['text_content'] else None
    
    def extract_ad_library_details(self, ad_element, ad_data):
        """Extract Facebook Ad Library specific details"""
        try:
            # Look for "See Ad Details" or similar links
            detail_links = ad_element.find_elements(By.CSS_SELECTOR, "a[href*='ad_archive_id']")
            if detail_links:
                ad_data['ad_details']['detail_url'] = detail_links[0].get_attribute('href')
            
            # Look for date information
            date_elements = ad_element.find_elements(By.CSS_SELECTOR, "*[data-testid*='date'], time")
            for date_elem in date_elements:
                date_text = date_elem.get_attribute('datetime') or date_elem.text
                if date_text:
                    ad_data['ad_details']['date_info'] = date_text
                    break
                    
        except Exception as e:
            print(f"Error extracting ad library details: {e}")
    
    def scroll_to_load_content(self, max_scrolls=None):
        """Scroll down to load more ads"""
        if max_scrolls is None:
            max_scrolls = SCRAPING_CONFIG.get("scroll_attempts", 5)
        print("Scrolling to load more content...")
        
        for i in range(max_scrolls):
            # Get current page height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content to load
            time.sleep(3)
            
            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"No new content loaded after scroll {i+1}")
                break
            else:
                print(f"Scroll {i+1}: New content loaded")
    
    def scrape_competitor_ads(self, competitor_name, page_id, countries=None):
        """
        Scrape ads for a specific competitor globally (using ALL countries)
        
        Args:
            competitor_name (str): Name of the competitor
            page_id (str): Facebook page ID
            countries (list): List of country codes to search (default: self.target_countries)
        """
        if countries is None:
            countries = self.target_countries
            
        competitor_data = {
            'competitor': competitor_name,
            'page_id': page_id,
            'countries_scraped': [],
            'total_ads_found': 0,
            'ads_by_country': {},
            'scrape_timestamp': datetime.now().isoformat()
        }
        
        print(f"\n🔍 Scraping ads for {competitor_name} (Page ID: {page_id})")
        print(f"Searching globally across ALL countries...")
        
        # Since we're using "ALL", we only need one iteration
        country = countries[0]  # Should be "ALL"
        print(f"\n🌍 Performing global search...")
        
        try:
            url = self.build_ads_url(page_id, country)
            self.driver.get(url)
            
            if not self.wait_for_page_load():
                print(f"❌ Failed to load global ads page")
                return competitor_data
            
            # Take screenshot for debugging if enabled
            if SCRAPING_CONFIG.get("screenshot_debug", True):
                screenshot_path = f"{self.screenshot_dir}/{competitor_name}_{country}.png"
                self.driver.save_screenshot(screenshot_path)
            
            has_ads, status_msg = self.check_for_ads()
            print(f"   {status_msg}")
            
            if has_ads:
                ads_data = self.extract_ad_data()
                if ads_data:
                    # Filter for top-performing ads from this competitor
                    filtered_ads = self.filter_top_performing_ads(ads_data, competitor_name)
                    
                    competitor_data['countries_scraped'].append(country)
                    competitor_data['ads_by_country'][country] = filtered_ads
                    competitor_data['total_ads_found'] = len(filtered_ads)
                    self.all_ads_data.extend([{**ad, 'competitor': competitor_name, 'country': 'GLOBAL'} for ad in filtered_ads])
                    print(f"   ✅ Selected {len(filtered_ads)} top-performing ads from {competitor_name}")
                    print(f"   📊 Filtered from {len(ads_data)} total ads found")
                else:
                    print(f"   ⚠️  No ads extracted globally")
            else:
                print(f"   ❌ No ads found globally")
            
        except Exception as e:
            print(f"   ❌ Error scraping globally: {e}")
        
        print(f"\n📊 Summary for {competitor_name}:")
        print(f"   Global search completed")
        print(f"   Top-performing ads selected: {competitor_data['total_ads_found']}")
        
        return competitor_data
    
    def calculate_performance_score(self, ad):
        """Calculate performance score for a single ad"""
        score = 0
        
        # Text content length (longer might indicate more detailed/engaging content)
        if ad.get('text_content'):
            text_weight = PERFORMANCE_WEIGHTS.get("text_length", 0.1)
            score += len(ad['text_content']) * text_weight
        
        # Media presence
        if ad.get('media_urls'):
            media_weight = PERFORMANCE_WEIGHTS.get("media_count", 2.0)
            score += len(ad['media_urls']) * media_weight
        
        # Engagement metrics (if any numbers can be extracted)
        engagement_text = str(ad.get('engagement_metrics', {}))
        numbers = re.findall(r'\d+', engagement_text)
        if numbers:
            # Sum all numbers found in engagement text
            engagement_sum = sum(int(num) for num in numbers)
            engagement_weight = PERFORMANCE_WEIGHTS.get("engagement_numbers", 1.0)
            score += engagement_sum * engagement_weight
        
        # CTA presence
        if ad.get('cta_button'):
            cta_weight = PERFORMANCE_WEIGHTS.get("cta_presence", 5.0)
            score += cta_weight
        
        # Link presence  
        if ad.get('link_url'):
            link_weight = PERFORMANCE_WEIGHTS.get("link_presence", 3.0)
            score += link_weight
            
        return round(score, 2)
    
    def filter_top_performing_ads(self, ads_data, competitor_name):
        """Filter ads to return only the top N performing ones for this competitor"""
        top_count = SCRAPING_CONFIG.get("top_ads_per_competitor", 10)
        min_threshold = SCRAPING_CONFIG.get("min_performance_threshold", 0)
        
        print(f"🎯 Filtering {len(ads_data)} ads for {competitor_name} (top {top_count} performers)...")
        
        # Calculate performance scores for all ads
        for ad in ads_data:
            ad['performance_score'] = self.calculate_performance_score(ad)
        
        # Sort by performance score (highest first)
        sorted_ads = sorted(ads_data, key=lambda x: x.get('performance_score', 0), reverse=True)
        
        # First filter by minimum threshold, then take top N
        threshold_filtered = [ad for ad in sorted_ads if ad.get('performance_score', 0) >= min_threshold]
        top_ads = threshold_filtered[:top_count]
        
        print(f"📊 Performance summary for {competitor_name}:")
        print(f"   Total ads analyzed: {len(ads_data)}")
        print(f"   Ads above threshold ({min_threshold}): {len(threshold_filtered)}")
        print(f"   Top performers selected: {len(top_ads)}")
        if top_ads:
            print(f"   Best score: {max(ad.get('performance_score', 0) for ad in top_ads)}")
            print(f"   Worst score in top: {min(ad.get('performance_score', 0) for ad in top_ads)}")
            print(f"   Average score: {round(sum(ad.get('performance_score', 0) for ad in top_ads) / len(top_ads), 2)}")
        
        return top_ads
    
    def analyze_top_performing_ads(self, min_engagement_threshold=0):
        """Analyze and identify top-performing ads based on available metrics"""
        if not self.all_ads_data:
            print("No ads data available for analysis")
            return []
        
        print(f"\n📈 Analyzing {len(self.all_ads_data)} ads for performance...")
        
        # Score ads based on available metrics using config weights
        for ad in self.all_ads_data:
            if not ad.get('performance_score'):  # Only calculate if not already done
                ad['performance_score'] = self.calculate_performance_score(ad)
        
        # Sort by performance score
        sorted_ads = sorted(self.all_ads_data, key=lambda x: x.get('performance_score', 0), reverse=True)
        
        # Filter by threshold
        top_ads = [ad for ad in sorted_ads if ad.get('performance_score', 0) >= min_engagement_threshold]
        
        print(f"Found {len(top_ads)} ads meeting performance criteria")
        
        return top_ads
    
    def scrape_all_competitors(self):
        """Scrape top-performing ads for all competitors globally"""
        if not self.driver:
            self.start_driver()
        
        all_competitor_data = {}
        
        print("🚀 Starting global competitor ad scraping for TOP PERFORMERS PER COMPETITOR...")
        print(f"Competitors: {list(self.competitors.keys())}")
        print(f"Search scope: GLOBAL (ALL countries)")
        print(f"Top ads per competitor: {SCRAPING_CONFIG.get('top_ads_per_competitor', 10)}")
        print(f"Minimum performance threshold: {SCRAPING_CONFIG.get('min_performance_threshold', 0)}")
        
        for competitor, page_id in self.competitors.items():
            try:
                competitor_data = self.scrape_competitor_ads(competitor, page_id)
                all_competitor_data[competitor] = competitor_data
            except Exception as e:
                print(f"❌ Error scraping {competitor}: {e}")
                continue
        
        return all_competitor_data
    
    def export_data(self, output_dir=None):
        """Export scraped data to various formats"""
        if output_dir is None:
            output_dir = EXPORT_CONFIG.get("output_dir", "ad_data")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export top-performing ads to CSV
        if self.all_ads_data:
            csv_file = f"{output_dir}/top_performing_ads_{timestamp}.csv"
            
            # Flatten the data for CSV export
            flattened_data = []
            for ad in self.all_ads_data:
                flat_ad = {
                    'competitor': ad.get('competitor', ''),
                    'country': ad.get('country', ''),
                    'timestamp': ad.get('timestamp', ''),
                    'text_content': ad.get('text_content', ''),
                    'media_count': len(ad.get('media_urls', [])),
                    'media_urls': '|'.join(ad.get('media_urls', [])),
                    'cta_button': ad.get('cta_button', ''),
                    'link_url': ad.get('link_url', ''),
                    'performance_score': ad.get('performance_score', 0),
                    'engagement_metrics': str(ad.get('engagement_metrics', {})),
                    'ad_details': str(ad.get('ad_details', {}))
                }
                flattened_data.append(flat_ad)
            
            df = pd.DataFrame(flattened_data)
            df.to_csv(csv_file, index=False, encoding='utf-8')
            print(f"📄 Exported top-performing ads per competitor to: {csv_file}")
        
        # Export top performing ads
        top_ads = self.analyze_top_performing_ads()
        if top_ads:
            top_ads_file = f"{output_dir}/top_performing_ads_{timestamp}.json"
            max_top_ads = EXPORT_CONFIG.get("max_top_ads", 100)
            with open(top_ads_file, 'w', encoding='utf-8') as f:
                json.dump(top_ads[:max_top_ads], f, indent=2, ensure_ascii=False)
            print(f"🏆 Exported top performing ads to: {top_ads_file}")
        
        # Export summary report
        summary = {
            'scrape_timestamp': datetime.now().isoformat(),
            'search_scope': 'GLOBAL',
            'approach': 'TOP_PERFORMERS_PER_COMPETITOR',
            'top_ads_per_competitor': SCRAPING_CONFIG.get('top_ads_per_competitor', 10),
            'performance_threshold': SCRAPING_CONFIG.get('min_performance_threshold', 0),
            'total_top_performing_ads': len(self.all_ads_data),
            'competitors_scraped': list(set(ad.get('competitor', '') for ad in self.all_ads_data)),
            'top_performing_count': len(top_ads),
            'summary_by_competitor': {}
        }
        
        for competitor in summary['competitors_scraped']:
            competitor_ads = [ad for ad in self.all_ads_data if ad.get('competitor') == competitor]
            if competitor_ads:
                scores = [ad.get('performance_score', 0) for ad in competitor_ads]
                summary['summary_by_competitor'][competitor] = {
                    'total_top_performing_ads': len(competitor_ads),
                    'avg_performance_score': round(sum(scores) / len(scores), 2),
                    'max_performance_score': round(max(scores), 2),
                    'min_performance_score': round(min(scores), 2)
                }
        
        summary_file = f"{output_dir}/scraping_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"📊 Exported summary report to: {summary_file}")
        
        return {
            'csv_file': csv_file if self.all_ads_data else None,
            'top_ads_file': top_ads_file if top_ads else None,
            'summary_file': summary_file
        }

def main():
    """Main function to run the scraper"""
    scraper = FacebookAdLibraryScraper()  # Uses headless setting from config
    
    try:
        # Start the scraping process
        scraper.start_driver()
        
        # Scrape all competitors
        all_data = scraper.scrape_all_competitors()
        
        # Export the data
        exported_files = scraper.export_data()
        
        print("\n🎉 Scraping completed!")
        print("📁 Exported files:")
        for file_type, file_path in exported_files.items():
            if file_path:
                print(f"   {file_type}: {file_path}")
        
    except Exception as e:
        print(f"❌ Error in main process: {e}")
    finally:
        scraper.stop_driver()

if __name__ == "__main__":
    main() 