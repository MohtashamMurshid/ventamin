"""
Scraping module for Facebook Ad Library data extraction
"""

from .facebook_ad_scraper import FacebookAdLibraryScraper
from .config import COMPETITORS, TARGET_COUNTRIES, SCRAPING_CONFIG, EXPORT_CONFIG

__all__ = [
    'FacebookAdLibraryScraper',
    'COMPETITORS',
    'TARGET_COUNTRIES', 
    'SCRAPING_CONFIG',
    'EXPORT_CONFIG'
] 