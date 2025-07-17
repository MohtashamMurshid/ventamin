#!/usr/bin/env python3
"""
Facebook Ad Library Scraper Runner

This script runs the Facebook Ad Library scraper for competitor analysis.
"""

from .facebook_ad_scraper import FacebookAdLibraryScraper
from .config import COMPETITORS, TARGET_COUNTRIES, SCRAPING_CONFIG, EXPORT_CONFIG
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='Run Facebook Ad Library Scraper')
    parser.add_argument('--competitors', nargs='+', choices=list(COMPETITORS.keys()) + ['all'], 
                        default=['all'], help='Competitors to scrape (default: all)')
    parser.add_argument('--countries', nargs='+', default=TARGET_COUNTRIES[:10],  # First 10 countries by default
                        help='Countries to search (default: top 10 markets)')
    parser.add_argument('--headless', action='store_true', 
                        help='Run browser in headless mode')
    parser.add_argument('--quick', action='store_true',
                        help='Quick mode: search only US, UK, CA, AU')
    parser.add_argument('--output-dir', default=EXPORT_CONFIG['output_dir'],
                        help='Output directory for results')
    
    args = parser.parse_args()
    
    # Validate page IDs
    missing_ids = []
    for comp in COMPETITORS:
        if 'PLACEHOLDER' in COMPETITORS[comp]:
            missing_ids.append(comp)
    
    if missing_ids:
        print("⚠️  WARNING: The following competitors have placeholder page IDs:")
        for comp in missing_ids:
            print(f"   {comp}: {COMPETITORS[comp]}")
        print("\nPlease update the page IDs in config.py before running the scraper.")
        print("You can still run the scraper, but these competitors will be skipped.")
        
        response = input("\nDo you want to continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Exiting. Please update config.py with actual page IDs.")
            sys.exit(1)
    
    # Set up competitors to scrape
    if args.competitors == ['all']:
        competitors_to_scrape = COMPETITORS
    else:
        competitors_to_scrape = {comp: COMPETITORS[comp] for comp in args.competitors if comp in COMPETITORS}
    
    # Set up countries
    if args.quick:
        countries = ['US', 'GB', 'CA', 'AU']
        print("🚀 Quick mode: Searching US, UK, Canada, Australia only")
    else:
        countries = args.countries
    
    print(f"\n📋 Scraping Configuration:")
    print(f"   Competitors: {list(competitors_to_scrape.keys())}")
    print(f"   Countries: {len(countries)} regions")
    print(f"   Headless mode: {args.headless or SCRAPING_CONFIG['headless']}")
    print(f"   Output directory: {args.output_dir}")
    
    # Initialize scraper
    scraper = FacebookAdLibraryScraper(
        headless=args.headless or SCRAPING_CONFIG['headless'],
        screenshot_dir=f"{args.output_dir}/screenshots"
    )
    
    # Override competitor list and countries
    scraper.competitors = competitors_to_scrape
    scraper.target_countries = countries
    
    try:
        print("\n🎯 Starting scraper...")
        scraper.start_driver()
        
        # Scrape all competitors
        all_data = scraper.scrape_all_competitors()
        
        # Export the data
        exported_files = scraper.export_data(args.output_dir)
        
        print("\n✅ Scraping completed successfully!")
        print(f"\n📊 Results Summary:")
        print(f"   Total ads found: {len(scraper.all_ads_data)}")
        
        # Summary by competitor
        for comp in competitors_to_scrape:
            comp_ads = [ad for ad in scraper.all_ads_data if ad.get('competitor') == comp]
            countries_with_ads = list(set(ad.get('country') for ad in comp_ads))
            print(f"   {comp}: {len(comp_ads)} ads across {len(countries_with_ads)} countries")
        
        print(f"\n📁 Exported files:")
        for file_type, file_path in exported_files.items():
            if file_path:
                print(f"   📄 {file_type}: {file_path}")
        
        # Show top performing ads summary
        top_ads = scraper.analyze_top_performing_ads()
        if top_ads:
            print(f"\n🏆 Top 5 Performing Ads:")
            for i, ad in enumerate(top_ads[:5], 1):
                competitor = ad.get('competitor', 'Unknown')
                country = ad.get('country', 'Unknown')
                score = ad.get('performance_score', 0)
                text_preview = ad.get('text_content', '')[:100] + "..." if len(ad.get('text_content', '')) > 100 else ad.get('text_content', '')
                print(f"   {i}. {competitor} ({country}) - Score: {score}")
                print(f"      \"{text_preview}\"")
        
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.stop_driver()
        print("\n🔒 Browser closed")

if __name__ == "__main__":
    main() 