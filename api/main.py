#!/usr/bin/env python3
"""
FastAPI Backend for Competitor Ad Analysis
Integrates Facebook Ad Library Scraper and Media Analysis
"""

import os
# Set matplotlib backend before importing pyplot to avoid GUI issues
os.environ['MPLBACKEND'] = 'Agg'

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import json
import logging
from datetime import datetime
import uuid

# Import your existing modules
from scraping.facebook_ad_scraper import FacebookAdLibraryScraper
from scraping.config import COMPETITORS, TARGET_COUNTRIES, SCRAPING_CONFIG, EXPORT_CONFIG

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="Competitor Ad Analysis API",
    description="API for scraping and analyzing competitor ads from Facebook Ad Library",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Next.js default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API schemas
class AdData(BaseModel):
    index: int
    competitor: str
    country: str
    timestamp: str
    text_content: str
    media_urls: List[str]
    performance_score: float
    cta_button: Optional[str] = None
    link_url: Optional[str] = None

class ScrapingRequest(BaseModel):
    competitors: List[str] = Field(default=["all"], description="List of competitors to scrape or 'all'")
    countries: List[str] = Field(default=["ALL"], description="List of countries to search")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    quick_mode: bool = Field(default=False, description="Quick mode for testing")
    max_ads: int = Field(default=10, description="Maximum ads to return per competitor")

class ScrapingResponse(BaseModel):
    task_id: str
    message: str
    status: str

class TopAdsResponse(BaseModel):
    total_ads: int
    ads: List[AdData]
    summary_by_competitor: Dict[str, Any]

class MediaAnalysisRequest(BaseModel):
    json_file_path: Optional[str] = None
    max_ads: int = Field(default=15, description="Maximum ads to analyze")
    use_latest: bool = Field(default=True, description="Use latest scraped data if no file specified")

class MediaAnalysisResponse(BaseModel):
    task_id: str
    message: str
    status: str
    analysis_results: Optional[Dict[str, Any]] = None

# In-memory storage for background tasks (in production, use Redis or database)
task_storage = {}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Competitor Ad Analysis API",
        "version": "1.0.0",
        "endpoints": {
            "scrape": "/scrape - Start scraping competitor ads",
            "top_ads": "/ads/top - Get top performing ads",
            "analyze_media": "/analyze/media - Run media analysis",
            "status": "/task/{task_id} - Check task status"
        }
    }

@app.get("/competitors")
async def get_competitors():
    """Get list of configured competitors"""
    return {
        "competitors": list(COMPETITORS.keys()),
        "page_ids": COMPETITORS
    }

@app.get("/ads/top", response_model=TopAdsResponse)
async def get_top_performing_ads(limit: int = Query(default=10, ge=1, le=100)):
    """Get top performing ads from latest scraping data"""
    try:
        # Find the latest ads file
        ad_data_dir = EXPORT_CONFIG.get("output_dir", "ad_data")
        if not os.path.exists(ad_data_dir):
            raise HTTPException(status_code=404, detail="No scraped data found. Run scraping first.")
        
        # Find latest JSON file
        json_files = [f for f in os.listdir(ad_data_dir) if f.startswith("top_performing_ads_") and f.endswith(".json")]
        if not json_files:
            raise HTTPException(status_code=404, detail="No ads data found. Run scraping first.")
        
        latest_file = max(json_files, key=lambda x: x.split("_")[-1].replace(".json", ""))
        file_path = os.path.join(ad_data_dir, latest_file)
        
        # Load and return top ads
        with open(file_path, 'r', encoding='utf-8') as f:
            ads_data = json.load(f)
        
        # Sort by performance score and limit
        sorted_ads = sorted(ads_data, key=lambda x: x.get('performance_score', 0), reverse=True)
        top_ads = sorted_ads[:limit]
        
        # Calculate summary by competitor
        summary = {}
        for competitor in COMPETITORS.keys():
            competitor_ads = [ad for ad in ads_data if ad.get('competitor') == competitor]
            if competitor_ads:
                scores = [ad.get('performance_score', 0) for ad in competitor_ads]
                summary[competitor] = {
                    "total_ads": len(competitor_ads),
                    "avg_score": round(sum(scores) / len(scores), 2),
                    "max_score": round(max(scores), 2),
                    "min_score": round(min(scores), 2)
                }
        
        return TopAdsResponse(
            total_ads=len(top_ads),
            ads=[AdData(**ad) for ad in top_ads],
            summary_by_competitor=summary
        )
        
    except Exception as e:
        logger.error(f"Error retrieving top ads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving ads: {str(e)}")

@app.post("/scrape", response_model=ScrapingResponse)
async def start_scraping(request: ScrapingRequest, background_tasks: BackgroundTasks):
    """Start background scraping task"""
    task_id = str(uuid.uuid4())
    
    # Store task info
    task_storage[task_id] = {
        "status": "started",
        "message": "Scraping task initiated",
        "start_time": datetime.now().isoformat(),
        "progress": 0,
        "results": None
    }
    
    # Add background task
    background_tasks.add_task(run_scraping_task, task_id, request)
    
    return ScrapingResponse(
        task_id=task_id,
        message="Scraping task started",
        status="started"
    )

@app.post("/analyze/media", response_model=MediaAnalysisResponse)
async def start_media_analysis(request: MediaAnalysisRequest, background_tasks: BackgroundTasks):
    """Start background media analysis task"""
    task_id = str(uuid.uuid4())
    
    # Determine file path
    if request.json_file_path:
        file_path = request.json_file_path
    elif request.use_latest:
        # Find latest file
        ad_data_dir = EXPORT_CONFIG.get("output_dir", "ad_data")
        if not os.path.exists(ad_data_dir):
            raise HTTPException(status_code=404, detail="No scraped data found. Run scraping first.")
        
        json_files = [f for f in os.listdir(ad_data_dir) if f.startswith("top_performing_ads_") and f.endswith(".json")]
        if not json_files:
            raise HTTPException(status_code=404, detail="No ads data found. Run scraping first.")
        
        latest_file = max(json_files, key=lambda x: x.split("_")[-1].replace(".json", ""))
        file_path = os.path.join(ad_data_dir, latest_file)
    else:
        raise HTTPException(status_code=400, detail="Must specify json_file_path or use_latest=True")
    
    # Store task info
    task_storage[task_id] = {
        "status": "started",
        "message": "Media analysis task initiated",
        "start_time": datetime.now().isoformat(),
        "progress": 0,
        "results": None
    }
    
    # Add background task
    background_tasks.add_task(run_media_analysis_task, task_id, file_path, request.max_ads)
    
    return MediaAnalysisResponse(
        task_id=task_id,
        message="Media analysis task started",
        status="started"
    )

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a background task"""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task_storage[task_id]

@app.get("/ads/latest-file")
async def get_latest_ads_file():
    """Get information about the latest ads data file"""
    try:
        ad_data_dir = EXPORT_CONFIG.get("output_dir", "ad_data")
        if not os.path.exists(ad_data_dir):
            return {"file": None, "message": "No data directory found"}
        
        json_files = [f for f in os.listdir(ad_data_dir) if f.startswith("top_performing_ads_") and f.endswith(".json")]
        if not json_files:
            return {"file": None, "message": "No ads data files found"}
        
        latest_file = max(json_files, key=lambda x: x.split("_")[-1].replace(".json", ""))
        file_path = os.path.join(ad_data_dir, latest_file)
        
        # Get file stats
        file_stat = os.stat(file_path)
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return {
            "file": latest_file,
            "path": file_path,
            "size": file_stat.st_size,
            "created": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            "total_ads": len(data)
        }
    except Exception as e:
        return {"file": None, "message": f"Error: {str(e)}"}

# Background task functions
async def run_scraping_task(task_id: str, request: ScrapingRequest):
    """Background task for running the scraper"""
    try:
        # Update task status
        task_storage[task_id]["status"] = "running"
        task_storage[task_id]["message"] = "Initializing scraper..."
        task_storage[task_id]["progress"] = 10
        
        # Set up competitors
        if request.competitors == ["all"]:
            competitors_to_scrape = COMPETITORS
        else:
            competitors_to_scrape = {comp: COMPETITORS[comp] for comp in request.competitors if comp in COMPETITORS}
        
        # Set up countries
        countries = ["US", "GB", "CA", "AU"] if request.quick_mode else request.countries
        
        # Initialize scraper
        scraper = FacebookAdLibraryScraper(headless=request.headless)
        scraper.competitors = competitors_to_scrape
        scraper.target_countries = countries
        
        task_storage[task_id]["progress"] = 20
        task_storage[task_id]["message"] = "Starting browser and scraping..."
        
        # Start scraping
        scraper.start_driver()
        
        # Scrape all competitors
        all_data = scraper.scrape_all_competitors()
        
        task_storage[task_id]["progress"] = 80
        task_storage[task_id]["message"] = "Exporting data..."
        
        # Export the data
        output_dir = EXPORT_CONFIG.get("output_dir", "ad_data")
        exported_files = scraper.export_data(output_dir)
        
        # Get top performing ads
        top_ads = scraper.analyze_top_performing_ads()[:request.max_ads]
        
        task_storage[task_id]["status"] = "completed"
        task_storage[task_id]["progress"] = 100
        task_storage[task_id]["message"] = "Scraping completed successfully"
        task_storage[task_id]["results"] = {
            "total_ads": len(scraper.all_ads_data),
            "top_ads_count": len(top_ads),
            "competitors_scraped": list(competitors_to_scrape.keys()),
            "exported_files": exported_files,
            "summary_by_competitor": {
                comp: len([ad for ad in scraper.all_ads_data if ad.get('competitor') == comp])
                for comp in competitors_to_scrape.keys()
            }
        }
        
        scraper.stop_driver()
        
    except Exception as e:
        logger.error(f"Scraping task {task_id} failed: {str(e)}")
        task_storage[task_id]["status"] = "failed"
        task_storage[task_id]["message"] = f"Scraping failed: {str(e)}"
        task_storage[task_id]["progress"] = 0

async def run_media_analysis_task(task_id: str, file_path: str, max_ads: int):
    """Background task for running media analysis"""
    try:
        # Import here to avoid matplotlib issues on startup
        from analysis.simple_media_analysis import SimpleMediaAnalyzer
        
        # Update task status
        task_storage[task_id]["status"] = "running"
        task_storage[task_id]["message"] = "Initializing media analyzer..."
        task_storage[task_id]["progress"] = 10
        
        # Initialize analyzer
        analyzer = SimpleMediaAnalyzer(file_path)
        
        task_storage[task_id]["progress"] = 20
        task_storage[task_id]["message"] = "Analyzing media URLs and downloading samples..."
        
        # Run analysis
        analyzer.analyze_media_urls(max_ads=max_ads)
        
        task_storage[task_id]["progress"] = 60
        task_storage[task_id]["message"] = "Generating insights and recommendations..."
        
        # Get analysis results
        df = analyzer.analyze_performance_vs_media_features()
        
        task_storage[task_id]["progress"] = 80
        task_storage[task_id]["message"] = "Creating visualizations..."
        
        # Create visualizations (this will save to disk)
        if df is not None:
            analyzer.create_media_visualizations(df)
        
        task_storage[task_id]["progress"] = 90
        task_storage[task_id]["message"] = "Saving results..."
        
        # Save results
        results_file = os.path.join(analyzer.output_dir, 'media_analysis_results.json')
        with open(results_file, 'w') as f:
            json.dump(analyzer.media_analysis_results, f, indent=2, default=str)
        
        task_storage[task_id]["status"] = "completed"
        task_storage[task_id]["progress"] = 100
        task_storage[task_id]["message"] = "Media analysis completed successfully"
        task_storage[task_id]["results"] = {
            "total_ads_analyzed": len(analyzer.media_analysis_results),
            "output_directory": analyzer.output_dir,
            "results_file": results_file,
            "visualizations_created": True,
            "media_samples_downloaded": True,
            "analysis_summary": {
                "video_usage_rate": len([ad for ad in analyzer.media_analysis_results if ad['media_analysis']['has_video']]) / len(analyzer.media_analysis_results) if analyzer.media_analysis_results else 0,
                "avg_media_per_ad": sum(ad['media_analysis']['total_media_count'] for ad in analyzer.media_analysis_results) / len(analyzer.media_analysis_results) if analyzer.media_analysis_results else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Media analysis task {task_id} failed: {str(e)}")
        task_storage[task_id]["status"] = "failed"
        task_storage[task_id]["message"] = f"Media analysis failed: {str(e)}"
        task_storage[task_id]["progress"] = 0

def main():
    """Main entry point for the API server"""
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main() 