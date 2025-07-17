# Competitor Ad Analysis API Documentation

## Overview

FastAPI backend for scraping and analyzing competitor ads from Facebook Ad Library. Designed to work seamlessly with Next.js frontends.

## Base URL

```
http://localhost:8000
```

## Endpoints

### 1. Get API Information

```http
GET /
```

**Response:**

```json
{
  "message": "Competitor Ad Analysis API",
  "version": "1.0.0",
  "endpoints": {
    "scrape": "/scrape - Start scraping competitor ads",
    "top_ads": "/ads/top - Get top performing ads",
    "analyze_media": "/analyze/media - Run media analysis",
    "status": "/task/{task_id} - Check task status"
  }
}
```

### 2. Get Configured Competitors

```http
GET /competitors
```

**Response:**

```json
{
  "competitors": ["AG1", "IM8", "Loop"],
  "page_ids": {
    "AG1": "183869772601",
    "IM8": "345914995276546",
    "Loop": "517850318391712"
  }
}
```

### 3. Get Top Performing Ads

```http
GET /ads/top?limit=10
```

**Query Parameters:**

- `limit` (optional): Number of ads to return (1-100, default: 10)

**Response:**

```json
{
  "total_ads": 10,
  "ads": [
    {
      "index": 0,
      "competitor": "AG1",
      "country": "GLOBAL",
      "timestamp": "2025-07-17T18:00:56.457125",
      "text_content": "AG1 by Athletic Greens\nSponsored\n‼️Tired of the Supplement Guessing Game?...",
      "media_urls": ["https://example.com/image1.jpg"],
      "performance_score": 246.2,
      "cta_button": "Learn More",
      "link_url": "https://example.com"
    }
  ],
  "summary_by_competitor": {
    "AG1": {
      "total_ads": 10,
      "avg_score": 194.4,
      "max_score": 246.2,
      "min_score": 179.8
    }
  }
}
```

### 4. Start Scraping Task

```http
POST /scrape
```

**Request Body:**

```json
{
  "competitors": ["AG1", "IM8"], // or ["all"] for all competitors
  "countries": ["US", "GB", "CA"], // or ["ALL"] for global search
  "headless": true,
  "quick_mode": false,
  "max_ads": 10
}
```

**Response:**

```json
{
  "task_id": "abc123-def456-ghi789",
  "message": "Scraping task started",
  "status": "started"
}
```

### 5. Start Media Analysis Task

```http
POST /analyze/media
```

**Request Body:**

```json
{
  "json_file_path": null, // null to use latest file
  "max_ads": 15,
  "use_latest": true
}
```

**Response:**

```json
{
  "task_id": "xyz123-abc456-def789",
  "message": "Media analysis task started",
  "status": "started"
}
```

### 6. Check Task Status

```http
GET /task/{task_id}
```

**Response:**

```json
{
  "status": "completed", // "started", "running", "completed", "failed"
  "message": "Scraping completed successfully",
  "start_time": "2025-01-15T10:30:00.000Z",
  "progress": 100, // 0-100
  "results": {
    "total_ads": 29,
    "top_ads_count": 10,
    "competitors_scraped": ["AG1", "IM8", "Loop"],
    "exported_files": {
      "csv": "ad_data/top_performing_ads_20250115_103000.csv",
      "json": "ad_data/top_performing_ads_20250115_103000.json"
    }
  }
}
```

### 7. Get Latest File Information

```http
GET /ads/latest-file
```

**Response:**

```json
{
  "file": "top_performing_ads_20250115_103000.json",
  "path": "ad_data/top_performing_ads_20250115_103000.json",
  "size": 125467,
  "created": "2025-01-15T10:30:00.000Z",
  "modified": "2025-01-15T10:32:15.000Z",
  "total_ads": 29
}
```

## Next.js Integration Examples

### React Hook for API Calls

```javascript
// hooks/useAdAnalysisAPI.js
import { useState, useEffect } from "react";

export const useAdAnalysisAPI = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const baseURL = "http://localhost:8000";

  const startScraping = async (config) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${baseURL}/scrape`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error("Scraping failed");

      const data = await response.json();
      setLoading(false);
      return data;
    } catch (err) {
      setError(err.message);
      setLoading(false);
      throw err;
    }
  };

  const getTopAds = async (limit = 10) => {
    try {
      const response = await fetch(`${baseURL}/ads/top?limit=${limit}`);
      if (!response.ok) throw new Error("Failed to fetch ads");
      return await response.json();
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const startMediaAnalysis = async (config) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${baseURL}/analyze/media`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error("Media analysis failed");

      const data = await response.json();
      setLoading(false);
      return data;
    } catch (err) {
      setError(err.message);
      setLoading(false);
      throw err;
    }
  };

  const checkTaskStatus = async (taskId) => {
    try {
      const response = await fetch(`${baseURL}/task/${taskId}`);
      if (!response.ok) throw new Error("Task not found");
      return await response.json();
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  return {
    loading,
    error,
    startScraping,
    getTopAds,
    startMediaAnalysis,
    checkTaskStatus,
  };
};
```

### Component Example

```javascript
// components/AdDashboard.js
import { useState, useEffect } from "react";
import { useAdAnalysisAPI } from "../hooks/useAdAnalysisAPI";

export default function AdDashboard() {
  const [ads, setAds] = useState([]);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const { loading, error, startScraping, getTopAds, checkTaskStatus } =
    useAdAnalysisAPI();

  // Load initial ads
  useEffect(() => {
    loadTopAds();
  }, []);

  // Poll task status
  useEffect(() => {
    if (
      taskId &&
      taskStatus?.status !== "completed" &&
      taskStatus?.status !== "failed"
    ) {
      const interval = setInterval(async () => {
        try {
          const status = await checkTaskStatus(taskId);
          setTaskStatus(status);

          if (status.status === "completed") {
            loadTopAds(); // Refresh ads when scraping completes
          }
        } catch (err) {
          console.error("Error checking task status:", err);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [taskId, taskStatus]);

  const loadTopAds = async () => {
    try {
      const data = await getTopAds(10);
      setAds(data.ads);
    } catch (err) {
      console.error("Error loading ads:", err);
    }
  };

  const handleStartScraping = async () => {
    try {
      const result = await startScraping({
        competitors: ["all"],
        countries: ["ALL"],
        headless: true,
        quick_mode: false,
        max_ads: 10,
      });

      setTaskId(result.task_id);
      setTaskStatus({ status: "started", progress: 0 });
    } catch (err) {
      console.error("Error starting scraping:", err);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Ad Analysis Dashboard</h1>

      <div className="mb-6">
        <button
          onClick={handleStartScraping}
          disabled={loading || (taskStatus && taskStatus.status === "running")}
          className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50"
        >
          {loading ? "Starting..." : "Start New Scraping"}
        </button>

        {taskStatus && (
          <div className="mt-4 p-4 bg-gray-100 rounded">
            <p>Status: {taskStatus.status}</p>
            <p>Progress: {taskStatus.progress}%</p>
            <p>Message: {taskStatus.message}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {ads.map((ad, index) => (
          <div key={index} className="border rounded-lg p-4">
            <h3 className="font-bold">{ad.competitor}</h3>
            <p className="text-sm text-gray-600">
              Score: {ad.performance_score}
            </p>
            <p className="mt-2">{ad.text_content.substring(0, 100)}...</p>
            {ad.media_urls.length > 0 && (
              <p className="text-sm">Media: {ad.media_urls.length} items</p>
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
          Error: {error}
        </div>
      )}
    </div>
  );
}
```

## Running the API

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Using gunicorn
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Interactive API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Error Handling

All endpoints return proper HTTP status codes:

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (task or data not found)
- `500` - Internal Server Error

Error responses include detailed messages:

```json
{
  "detail": "No scraped data found. Run scraping first."
}
```

## CORS Configuration

The API is configured to work with Next.js development servers running on:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

For production, update the `allow_origins` list in `main.py`.
