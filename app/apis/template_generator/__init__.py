from fastapi import APIRouter, Response, HTTPException
import databutton as db
import pandas as pd
import io

router = APIRouter(prefix="/template_generator")

# This file is kept for backward compatibility but the templates functionality 
# has been removed from the UI. This API may be removed in a future update.

@router.get("/download/{platform}")
async def download_template(platform: str):
    """Download a template file for the specified platform."""
    try:
        csv_content = create_empty_template(platform)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={platform}_template.csv"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{platform}/sample")
async def download_sample(platform: str):
    """Download a sample file for the specified platform."""
    try:
        csv_content = create_sample_data(platform)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={platform}_sample.csv"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def create_empty_template(platform: str) -> str:
    """Create an empty template based on the platform."""
    platform = platform.lower()
    
    # Define columns based on platform
    if platform == "twitter":
        columns = ["date", "followers", "following", "engagement_rate", "likes", "replies", "retweets"]
    elif platform == "instagram":
        columns = ["date", "followers", "engagement", "likes", "comments", "shares", "posts"]
    elif platform == "facebook":
        columns = ["date", "page_total_likes", "post_impressions", "engaged_users", "page_engagement"]
    elif platform == "tiktok":
        columns = ["date", "followers", "views", "likes", "comments", "shares"]
    elif platform == "youtube":
        columns = ["date", "subscribers", "views", "watch_time", "likes", "comments"]
    else:
        # Generic template
        columns = ["date", "followers", "engagement", "likes", "comments", "shares"]
    
    # Create empty DataFrame
    df = pd.DataFrame(columns=columns)
    
    # Convert to CSV
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

def create_sample_data(platform: str) -> str:
    """Create sample data based on the platform."""
    platform = platform.lower()
    
    # Sample date range
    dates = pd.date_range(start="2023-01-01", periods=30)
    dates_str = [d.strftime("%Y-%m-%d") for d in dates]
    
    # Define sample data based on platform
    if platform == "twitter":
        # Twitter sample
        sample_data = {
            "date": dates_str,
            "followers": [10000 + i*50 for i in range(30)],
            "following": [1000 + i*2 for i in range(30)],
            "engagement_rate": [2.5 + (i*0.1) % 1 for i in range(30)],
            "likes": [500 + i*20 for i in range(30)],
            "replies": [50 + i*3 for i in range(30)],
            "retweets": [100 + i*5 for i in range(30)]
        }
    elif platform == "instagram":
        # Instagram sample
        sample_data = {
            "date": dates_str,
            "followers": [20000 + i*100 for i in range(30)],
            "engagement": [3.0 + (i*0.15) % 1.5 for i in range(30)],
            "likes": [1000 + i*30 for i in range(30)],
            "comments": [100 + i*5 for i in range(30)],
            "shares": [50 + i*4 for i in range(30)],
            "posts": [1 if i % 3 == 0 else 0 for i in range(30)]
        }
    elif platform == "facebook":
        # Facebook sample
        sample_data = {
            "date": dates_str,
            "page_total_likes": [15000 + i*80 for i in range(30)],
            "post_impressions": [5000 + i*150 for i in range(30)],
            "engaged_users": [800 + i*20 for i in range(30)],
            "page_engagement": [4.0 + (i*0.12) % 1 for i in range(30)]
        }
    elif platform == "tiktok":
        # TikTok sample
        sample_data = {
            "date": dates_str,
            "followers": [50000 + i*200 for i in range(30)],
            "views": [100000 + i*1000 for i in range(30)],
            "likes": [20000 + i*500 for i in range(30)],
            "comments": [1000 + i*30 for i in range(30)],
            "shares": [5000 + i*100 for i in range(30)]
        }
    elif platform == "youtube":
        # YouTube sample
        sample_data = {
            "date": dates_str,
            "subscribers": [100000 + i*300 for i in range(30)],
            "views": [50000 + i*1000 for i in range(30)],
            "watch_time": [10000 + i*500 for i in range(30)],
            "likes": [2000 + i*100 for i in range(30)],
            "comments": [500 + i*20 for i in range(30)]
        }
    else:
        # Generic sample
        sample_data = {
            "date": dates_str,
            "followers": [10000 + i*100 for i in range(30)],
            "engagement": [3.0 + (i*0.1) % 1 for i in range(30)],
            "likes": [500 + i*25 for i in range(30)],
            "comments": [100 + i*10 for i in range(30)],
            "shares": [50 + i*5 for i in range(30)]
        }
    
    # Create DataFrame
    df = pd.DataFrame(sample_data)
    
    # Convert to CSV
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()
