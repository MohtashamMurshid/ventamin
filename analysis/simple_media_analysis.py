import json
import pandas as pd
import requests
import numpy as np
from PIL import Image, ImageStat
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import os
from urllib.parse import urlparse
import time
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

class SimpleMediaAnalyzer:
    def __init__(self, json_file_path):
        """Initialize the media analyzer with competitor ads data"""
        with open(json_file_path, 'r', encoding='utf-8') as f:
            self.ads_data = json.load(f)
        
        # Create output directory for downloaded media
        self.output_dir = "media_analysis_output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize results storage
        self.media_analysis_results = []
        
    def analyze_media_urls(self, max_ads=None):
        """Analyze media URLs and download samples"""
        print("=" * 80)
        print("COMPETITOR AD MEDIA ANALYSIS")
        print("=" * 80)
        
        ads_to_analyze = self.ads_data[:max_ads] if max_ads else self.ads_data
        
        for i, ad in enumerate(ads_to_analyze):
            print(f"\nAnalyzing Ad {i+1}/{len(ads_to_analyze)} - Competitor: {ad.get('competitor', 'Unknown')}")
            print(f"Performance Score: {ad.get('performance_score', 0)}")
            
            media_urls = ad.get('media_urls', [])
            ad_analysis = {
                'ad_index': ad.get('index', i),
                'competitor': ad.get('competitor', 'Unknown'),
                'performance_score': ad.get('performance_score', 0),
                'text_content': ad.get('text_content', ''),
                'total_media_count': len(media_urls),
                'images': [],
                'videos': [],
                'media_analysis': {}
            }
            
            print(f"  Found {len(media_urls)} media items")
            
            for j, url in enumerate(media_urls):
                try:
                    print(f"  Processing media {j+1}/{len(media_urls)}: {url[:60]}...")
                    
                    # Determine media type from URL
                    url_lower = url.lower()
                    if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        analysis = self.analyze_image_url(url, ad['competitor'], i, j)
                        if analysis:
                            ad_analysis['images'].append(analysis)
                    elif any(ext in url_lower for ext in ['.mp4', '.mov', '.avi']) or 'video' in url_lower:
                        analysis = self.analyze_video_url(url, ad['competitor'], i, j)
                        if analysis:
                            ad_analysis['videos'].append(analysis)
                    else:
                        # Try to determine from content-type
                        analysis = self.analyze_unknown_media(url, ad['competitor'], i, j)
                        if analysis:
                            if analysis['type'] == 'image':
                                ad_analysis['images'].append(analysis)
                            else:
                                ad_analysis['videos'].append(analysis)
                    
                    # Add delay to be respectful to servers
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"    Error processing {url}: {str(e)}")
                    continue
            
            # Calculate aggregate metrics for this ad
            ad_analysis['media_analysis'] = self.calculate_ad_media_metrics(ad_analysis)
            self.media_analysis_results.append(ad_analysis)
            
        print(f"\nCompleted analysis of {len(self.media_analysis_results)} ads")
        
    def analyze_image_url(self, url, competitor, ad_idx, media_idx):
        """Analyze individual image properties"""
        try:
            # Download image with timeout
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code != 200:
                print(f"    Failed to download image: HTTP {response.status_code}")
                return None
                
            # Open image
            try:
                image = Image.open(BytesIO(response.content))
            except Exception as e:
                print(f"    Failed to open image: {str(e)}")
                return None
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Basic image properties
            width, height = image.size
            aspect_ratio = width / height if height > 0 else 0
            
            # Color analysis
            stat = ImageStat.Stat(image)
            avg_color = stat.mean  # RGB averages
            brightness = sum(avg_color) / 3
            
            # Calculate color dominance
            dominant_color = self.get_dominant_color_simple(image)
            
            # File size
            file_size = len(response.content)
            
            analysis = {
                'type': 'image',
                'url': url,
                'width': width,
                'height': height,
                'aspect_ratio': aspect_ratio,
                'brightness': brightness,
                'avg_red': avg_color[0],
                'avg_green': avg_color[1],
                'avg_blue': avg_color[2],
                'dominant_color': dominant_color,
                'file_size': file_size,
                'format': image.format
            }
            
            # Save image for manual inspection (downsized)
            try:
                # Resize for storage efficiency
                display_image = image.copy()
                display_image.thumbnail((400, 400), Image.Resampling.LANCZOS)
                
                filename = f"{competitor}_{ad_idx}_{media_idx}.jpg"
                filepath = os.path.join(self.output_dir, filename)
                display_image.save(filepath, 'JPEG', quality=85)
                analysis['saved_path'] = filepath
                print(f"    Saved: {filename}")
            except Exception as e:
                print(f"    Could not save image: {str(e)}")
            
            return analysis
            
        except Exception as e:
            print(f"    Image analysis error: {str(e)}")
            return None
    
    def analyze_video_url(self, url, competitor, ad_idx, media_idx):
        """Analyze video properties (metadata only)"""
        try:
            # Get video metadata without downloading full file
            response = requests.head(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            file_size = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', '')
            
            analysis = {
                'type': 'video',
                'url': url,
                'file_size': file_size,
                'content_type': content_type,
                'estimated_duration': self.estimate_video_duration(file_size),
                'format': self.extract_video_format(url, content_type)
            }
            
            print(f"    Video: {file_size/1024/1024:.1f}MB, {content_type}")
            return analysis
            
        except Exception as e:
            print(f"    Video analysis error: {str(e)}")
            return None
    
    def analyze_unknown_media(self, url, competitor, ad_idx, media_idx):
        """Analyze media with unknown type"""
        try:
            response = requests.head(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            content_type = response.headers.get('content-type', '').lower()
            
            if 'image' in content_type:
                return self.analyze_image_url(url, competitor, ad_idx, media_idx)
            elif 'video' in content_type:
                return self.analyze_video_url(url, competitor, ad_idx, media_idx)
            else:
                print(f"    Unknown media type: {content_type}")
                return None
                
        except Exception as e:
            print(f"    Unknown media analysis error: {str(e)}")
            return None
    
    def get_dominant_color_simple(self, image):
        """Get dominant color using simple method"""
        try:
            # Resize image for faster processing
            image_small = image.resize((50, 50))
            colors = image_small.getcolors(2500)
            if colors:
                # Get most frequent color
                dominant = max(colors, key=lambda x: x[0])
                return dominant[1]  # RGB tuple
            return None
        except:
            return None
    
    def estimate_video_duration(self, file_size):
        """Estimate video duration based on file size (rough estimate)"""
        if file_size == 0:
            return "unknown"
        
        # Very rough estimation: assume ~1MB per 30 seconds for social media video
        estimated_seconds = (file_size / 1024 / 1024) * 30
        
        if estimated_seconds < 30:
            return "short (< 30s)"
        elif estimated_seconds < 60:
            return "medium (30-60s)"
        else:
            return "long (> 60s)"
    
    def extract_video_format(self, url, content_type):
        """Extract video format from URL or content type"""
        if '.mp4' in url.lower():
            return 'mp4'
        elif '.mov' in url.lower():
            return 'mov'
        elif '.avi' in url.lower():
            return 'avi'
        elif 'mp4' in content_type:
            return 'mp4'
        else:
            return 'unknown'
    
    def calculate_ad_media_metrics(self, ad_analysis):
        """Calculate aggregate metrics for an ad's media"""
        images = ad_analysis['images']
        videos = ad_analysis['videos']
        
        metrics = {
            'image_count': len(images),
            'video_count': len(videos),
            'total_media_count': len(images) + len(videos),
            'avg_brightness': np.mean([img.get('brightness', 0) for img in images]) if images else 0,
            'avg_aspect_ratio': np.mean([item.get('aspect_ratio', 0) for item in images + videos if item.get('aspect_ratio', 0) > 0]),
            'total_file_size': sum(item.get('file_size', 0) for item in images + videos),
            'has_video': len(videos) > 0,
            'has_image': len(images) > 0,
            'media_mix': 'video_only' if len(videos) > 0 and len(images) == 0 else 
                        'image_only' if len(images) > 0 and len(videos) == 0 else
                        'mixed' if len(images) > 0 and len(videos) > 0 else 'none',
            'avg_image_size': np.mean([img.get('file_size', 0) for img in images]) if images else 0,
            'avg_video_size': np.mean([vid.get('file_size', 0) for vid in videos]) if videos else 0
        }
        
        return metrics
    
    def analyze_performance_vs_media_features(self):
        """Analyze correlation between media features and performance"""
        print("\n" + "=" * 50)
        print("MEDIA FEATURES vs PERFORMANCE ANALYSIS")
        print("=" * 50)
        
        # Create DataFrame for analysis
        analysis_data = []
        for ad in self.media_analysis_results:
            metrics = ad['media_analysis']
            analysis_data.append({
                'competitor': ad['competitor'],
                'performance_score': ad['performance_score'],
                'image_count': metrics['image_count'],
                'video_count': metrics['video_count'],
                'total_media_count': metrics['total_media_count'],
                'avg_brightness': metrics['avg_brightness'],
                'avg_aspect_ratio': metrics['avg_aspect_ratio'] if not np.isnan(metrics['avg_aspect_ratio']) else 0,
                'total_file_size': metrics['total_file_size'],
                'has_video': metrics['has_video'],
                'has_image': metrics['has_image'],
                'media_mix': metrics['media_mix'],
                'avg_image_size': metrics['avg_image_size'],
                'avg_video_size': metrics['avg_video_size']
            })
        
        df = pd.DataFrame(analysis_data)
        
        if len(df) == 0:
            print("No media analysis data available")
            return None
        
        # Performance correlations
        numeric_cols = ['image_count', 'video_count', 'total_media_count', 'avg_brightness', 
                       'avg_aspect_ratio', 'total_file_size']
        
        print("\nMEDIA FEATURE CORRELATIONS WITH PERFORMANCE:")
        for col in numeric_cols:
            if col in df.columns and df[col].nunique() > 1:
                corr = df[col].corr(df['performance_score'])
                print(f"  {col}: {corr:.3f}")
        
        # Media type performance analysis
        print(f"\nMEDIA TYPE PERFORMANCE ANALYSIS:")
        
        if 'has_video' in df.columns and df['has_video'].nunique() > 1:
            video_performance = df.groupby('has_video')['performance_score'].agg(['mean', 'count'])
            print(f"  Ads with video: {video_performance.loc[True, 'mean']:.1f} avg score ({video_performance.loc[True, 'count']} ads)")
            print(f"  Ads without video: {video_performance.loc[False, 'mean']:.1f} avg score ({video_performance.loc[False, 'count']} ads)")
        
        if 'media_mix' in df.columns:
            mix_performance = df.groupby('media_mix')['performance_score'].agg(['mean', 'count'])
            print(f"\nMEDIA MIX PERFORMANCE ANALYSIS:")
            for mix_type, stats in mix_performance.iterrows():
                print(f"  {mix_type.replace('_', ' ').title()}: {stats['mean']:.1f} avg score ({stats['count']} ads)")
        
        return df
    
    def generate_media_insights(self):
        """Generate insights about successful media strategies"""
        print("\n" + "=" * 50)
        print("MEDIA STRATEGY INSIGHTS")
        print("=" * 50)
        
        # Top performing ads analysis
        sorted_ads = sorted(self.media_analysis_results, key=lambda x: x['performance_score'], reverse=True)
        top_performers = sorted_ads[:5]
        
        print("TOP 5 PERFORMING ADS - MEDIA CHARACTERISTICS:")
        for i, ad in enumerate(top_performers):
            metrics = ad['media_analysis']
            print(f"\n{i+1}. {ad['competitor']} - Score: {ad['performance_score']:.1f}")
            print(f"   Media: {metrics['image_count']} images, {metrics['video_count']} videos")
            print(f"   Mix: {metrics['media_mix']}")
            print(f"   Total size: {metrics['total_file_size']/1024/1024:.1f}MB")
            if metrics['avg_brightness'] > 0:
                print(f"   Avg brightness: {metrics['avg_brightness']:.1f}")
        
        # Analyze by competitor
        competitor_insights = {}
        for ad in self.media_analysis_results:
            competitor = ad['competitor']
            if competitor not in competitor_insights:
                competitor_insights[competitor] = {
                    'ads': [],
                    'avg_performance': 0,
                    'media_patterns': {}
                }
            competitor_insights[competitor]['ads'].append(ad)
        
        # Calculate competitor insights
        for competitor, data in competitor_insights.items():
            ads = data['ads']
            data['avg_performance'] = np.mean([ad['performance_score'] for ad in ads])
            
            # Media patterns
            data['media_patterns'] = {
                'avg_images_per_ad': np.mean([ad['media_analysis']['image_count'] for ad in ads]),
                'avg_videos_per_ad': np.mean([ad['media_analysis']['video_count'] for ad in ads]),
                'video_usage_rate': np.mean([ad['media_analysis']['has_video'] for ad in ads]),
                'avg_total_size': np.mean([ad['media_analysis']['total_file_size'] for ad in ads]),
                'avg_brightness': np.mean([ad['media_analysis']['avg_brightness'] for ad in ads if ad['media_analysis']['avg_brightness'] > 0]),
                'common_media_mix': Counter([ad['media_analysis']['media_mix'] for ad in ads]).most_common(1)[0][0]
            }
        
        print(f"\nCOMPETITOR MEDIA STRATEGIES:")
        for competitor, data in sorted(competitor_insights.items(), key=lambda x: x[1]['avg_performance'], reverse=True):
            patterns = data['media_patterns']
            print(f"\n{competitor} (Avg Performance: {data['avg_performance']:.1f}):")
            print(f"  Images per ad: {patterns['avg_images_per_ad']:.1f}")
            print(f"  Videos per ad: {patterns['avg_videos_per_ad']:.1f}")
            print(f"  Video usage: {patterns['video_usage_rate']*100:.1f}%")
            print(f"  Avg total media size: {patterns['avg_total_size']/1024/1024:.1f}MB")
            print(f"  Common media mix: {patterns['common_media_mix']}")
            if patterns['avg_brightness'] > 0:
                print(f"  Avg brightness: {patterns['avg_brightness']:.1f}")
    
    def create_media_visualizations(self, df):
        """Create visualizations for media analysis"""
        if df is None or len(df) == 0:
            print("No data available for visualizations")
            return
            
        plt.style.use('default')
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. Performance vs Video Usage
        if 'has_video' in df.columns and df['has_video'].nunique() > 1:
            video_perf = df.groupby('has_video')['performance_score'].mean()
            axes[0,0].bar(['No Video', 'Has Video'], video_perf.values, color=['lightblue', 'orange'])
            axes[0,0].set_title('Performance: Video vs No Video')
            axes[0,0].set_ylabel('Average Performance Score')
        
        # 2. Performance vs Media Mix
        if 'media_mix' in df.columns:
            mix_perf = df.groupby('media_mix')['performance_score'].mean()
            axes[0,1].bar(range(len(mix_perf)), mix_perf.values, color=['lightcoral', 'lightgreen', 'gold'])
            axes[0,1].set_xticks(range(len(mix_perf)))
            axes[0,1].set_xticklabels([x.replace('_', ' ').title() for x in mix_perf.index], rotation=45)
            axes[0,1].set_title('Performance by Media Mix')
            axes[0,1].set_ylabel('Average Performance Score')
        
        # 3. Brightness vs Performance
        if 'avg_brightness' in df.columns and df['avg_brightness'].sum() > 0:
            bright_data = df[df['avg_brightness'] > 0]
            axes[0,2].scatter(bright_data['avg_brightness'], bright_data['performance_score'], alpha=0.6)
            axes[0,2].set_title('Brightness vs Performance')
            axes[0,2].set_xlabel('Average Brightness')
            axes[0,2].set_ylabel('Performance Score')
        
        # 4. Media Count Distribution
        axes[1,0].hist(df['total_media_count'], bins=max(1, len(df['total_media_count'].unique())), alpha=0.7, color='skyblue')
        axes[1,0].set_title('Total Media Count Distribution')
        axes[1,0].set_xlabel('Number of Media Items')
        axes[1,0].set_ylabel('Number of Ads')
        
        # 5. Performance by Competitor
        if len(df['competitor'].unique()) > 1:
            sns.boxplot(data=df, x='competitor', y='performance_score', ax=axes[1,1])
            axes[1,1].set_title('Performance by Competitor')
            axes[1,1].tick_params(axis='x', rotation=45)
        
        # 6. File Size vs Performance
        if 'total_file_size' in df.columns and df['total_file_size'].sum() > 0:
            size_mb = df['total_file_size'] / 1024 / 1024
            axes[1,2].scatter(size_mb, df['performance_score'], alpha=0.6, color='green')
            axes[1,2].set_title('Total File Size vs Performance')
            axes[1,2].set_xlabel('Total File Size (MB)')
            axes[1,2].set_ylabel('Performance Score')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'media_analysis_results.png'), dpi=300, bbox_inches='tight')
        plt.show()
    
    def generate_recommendations(self):
        """Generate actionable media recommendations"""
        print("\n" + "=" * 50)
        print("MEDIA STRATEGY RECOMMENDATIONS")
        print("=" * 50)
        
        # Analyze top performers
        sorted_ads = sorted(self.media_analysis_results, key=lambda x: x['performance_score'], reverse=True)
        top_third = sorted_ads[:len(sorted_ads)//3] if len(sorted_ads) >= 3 else sorted_ads
        
        if top_third:
            avg_images = np.mean([ad['media_analysis']['image_count'] for ad in top_third])
            avg_videos = np.mean([ad['media_analysis']['video_count'] for ad in top_third])
            video_usage = np.mean([ad['media_analysis']['has_video'] for ad in top_third])
            
            recommendations = [
                f"1. OPTIMAL MEDIA COUNT: Use {avg_images:.1f} images and {avg_videos:.1f} videos per ad on average",
                f"2. VIDEO STRATEGY: {video_usage*100:.1f}% of top performers include video content",
                f"3. MEDIA MIX: Analyze the most successful media combinations from top performers",
                "4. QUALITY FOCUS: Higher performing ads tend to use multiple media types",
                "5. COMPETITOR BENCHMARKING: Study AG1's media strategy as they show highest performance"
            ]
            
            for rec in recommendations:
                print(f"  {rec}")
        
        print(f"\nKEY INSIGHTS:")
        print(f"  - Total ads analyzed: {len(self.media_analysis_results)}")
        print(f"  - Images downloaded and saved to: {self.output_dir}/")
        print(f"  - Manual inspection of saved images recommended for deeper insights")
    
    def run_complete_analysis(self, max_ads=15):
        """Run the complete media analysis"""
        print("Starting simplified media analysis...")
        print(f"Note: Analyzing first {max_ads} ads to manage processing time")
        
        # Analyze media URLs
        self.analyze_media_urls(max_ads=max_ads)
        
        # Perform analysis
        df = self.analyze_performance_vs_media_features()
        self.generate_media_insights()
        
        # Create visualizations
        if df is not None:
            self.create_media_visualizations(df)
        
        self.generate_recommendations()
        
        # Save results
        results_file = os.path.join(self.output_dir, 'media_analysis_results.json')
        with open(results_file, 'w') as f:
            json.dump(self.media_analysis_results, f, indent=2, default=str)
        
        print(f"\n" + "=" * 80)
        print("MEDIA ANALYSIS COMPLETE")
        print(f"Results saved to: {self.output_dir}/")
        print(f"Downloaded media samples saved for manual inspection")
        print(f"Analysis data: {results_file}")
        print("=" * 80)
        
        return df

# Run the analysis
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = SimpleMediaAnalyzer('ad_data/top_performing_ads_20250717_180056.json')
    
    # Run analysis (limit to 15 ads for initial analysis)
    analyzer.run_complete_analysis(max_ads=15) 