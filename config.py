# Configuration file for Facebook Ad Library Scraper

# Competitor Facebook Page IDs
# Replace these placeholders with actual page IDs
COMPETITORS = {
    "AG1": "183869772601",  # Athletic Greens (example - replace with actual)
    "IM8": "345914995276546",  # IM8 page ID
    "Loop": "1577323122589954"  # Loop page ID
}

# Use "ALL" for global search instead of individual countries
# This searches all countries at once for better performance
TARGET_COUNTRIES = ["ALL"]

# Scraping settings - optimized for top-performing ads per competitor
SCRAPING_CONFIG = {
    "headless": False,  # Set to True to run browser in background
    "max_ads_per_country": 100,  # Increased limit to get more ads for better filtering
    "scroll_attempts": 8,  # More scrolling to load top ads
    "wait_timeout": 20,  # Longer timeout for global search
    "delay_between_countries": 1,  # Reduced since we're only doing one global search
    "screenshot_debug": True,  # Save screenshots for debugging
    "top_ads_per_competitor": 10,  # Number of top ads to keep per competitor
    "min_performance_threshold": 5.0  # Minimum threshold to consider an ad
}

# Export settings - focused on top performers per competitor
EXPORT_CONFIG = {
    "output_dir": "ad_data",
    "export_formats": ["csv", "json"],  # Available: csv, json, excel
    "max_top_ads": 100,  # Maximum top ads to export (across all competitors)
    "include_media_urls": True
}

# Performance scoring weights - tuned for identifying top performers
PERFORMANCE_WEIGHTS = {
    "text_length": 0.2,  # Increased weight for comprehensive text
    "media_count": 5.0,  # Higher weight for rich media content
    "engagement_numbers": 2.0,  # Higher weight for engagement metrics
    "cta_presence": 10.0,  # Strong bonus for CTA (indicates conversion focus)
    "link_presence": 8.0   # High bonus for external links (indicates campaign)
} 