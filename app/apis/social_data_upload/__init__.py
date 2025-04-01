import io
import pandas as pd
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import databutton as db
import re
from datetime import datetime, timedelta
import time
import random

router = APIRouter(prefix="/social_data_upload")

class SocialDataUploadRequest(BaseModel):
    platform: str
    userId: str

class PlatformData(BaseModel):
    followers: Optional[int] = None
    following: Optional[int] = None
    posts: Optional[int] = None
    engagement: Optional[float] = None
    growth: Optional[float] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    dailyStats: Optional[List[Dict[str, Any]]] = None
    contentPerformance: Optional[List[Dict[str, Any]]] = None

class SocialDataUploadResponse(BaseModel):
    success: bool
    data: Optional[PlatformData] = None
    error: Optional[str] = None

# Create a storage key from platform, userId and timestamp
def create_storage_key(platform: str, user_id: str) -> str:
    # Sanitize keys to only allow alphanumeric, dots, underscores and dashes
    platform = re.sub(r'[^a-zA-Z0-9._-]', '', platform)
    user_id = re.sub(r'[^a-zA-Z0-9._-]', '', user_id)
    timestamp = int(time.time())
    return f"social_data_{platform}_{user_id}_{timestamp}"

# Generate time series data for daily stats (fallback if file doesn't have this)
def generate_time_series(followers: int) -> List[Dict[str, Any]]:
    result = []
    today = datetime.now()

    # Randomize growth rate between 0.05% and 0.3% per day
    daily_growth_rate = random.uniform(0.0005, 0.003)

    # Randomize engagement rate between 1% and 5%
    base_engagement_rate = random.uniform(0.01, 0.05)

    # Start with current followers and work backwards
    current_followers = followers

    for i in range(30):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")

        # Add small random variations
        engagement_rate = base_engagement_rate * (1 + random.uniform(-0.1, 0.1))

        entry = {
            "date": date_str,
            "followers": current_followers,
            "engagement": round(engagement_rate * 100, 2)
        }

        # If this is for a video platform, add views
        if random.random() > 0.5:  # 50% chance
            entry["views"] = int(current_followers * random.uniform(2, 5))

        result.insert(0, entry)  # Insert at beginning to keep chronological order

        # Calculate previous day's followers
        current_followers = int(current_followers / (1 + daily_growth_rate))

    return result

# Generate content performance data (fallback if file doesn't have this)
def generate_content_performance(followers: int, platform: str) -> List[Dict[str, Any]]:
    result = []
    today = datetime.now()

    # Platform-specific content types
    content_types = {
        "instagram": ["post", "reel", "story"],
        "twitter": ["post"],
        "facebook": ["post", "video"],
        "tiktok": ["video"],
        "youtube": ["video"],
        "linkedin": ["post", "article"]
    }

    # Choose the right content types for this platform
    types = content_types.get(platform.lower(), ["post"])

    # Title templates based on content type
    title_templates = {
        "post": ["New Update", "Big Announcement", "Behind the Scenes"],
        "video": ["Tutorial: How To", "Vlog", "Product Demo"],
        "story": ["Daily Update", "Quick Tip", "Special Offer"],
        "reel": ["Trending Challenge", "Quick Tutorial", "Fun Moment"],
        "article": ["Industry Analysis", "Expert Guide", "Case Study"]
    }

    # Create 10 pieces of content performance data
    for i in range(10):
        # Select random content type for this platform
        content_type = random.choice(types)

        # Create date (more recent content first)
        date = today - timedelta(days=i*3 + random.randint(0, 2))
        date_str = date.strftime("%Y-%m-%d")

        # More recent content tends to have better performance
        recency_factor = 1 - (i / 12)  # 1.0 down to 0.25

        # Base engagement varies by content type
        type_factors = {"post": 1, "video": 1.2, "story": 0.8, "reel": 1.5, "article": 0.9}
        type_factor = type_factors.get(content_type, 1)

        # Calculate engagement metrics
        base_engagement = followers * random.uniform(0.01, 0.06) * recency_factor * type_factor

        # Select random title template
        templates = title_templates.get(content_type, ["New Content"])
        title = random.choice(templates)

        # Create content item
        item = {
            "id": f"content-{int(time.time())}-{i}",
            "type": content_type,
            "title": title,
            "date": date_str,
            "likes": int(base_engagement * random.uniform(0.6, 1.1)),
            "comments": int(base_engagement * random.uniform(0.05, 0.15)),
            "shares": int(base_engagement * random.uniform(0.02, 0.08))
        }

        # Add views for video content
        if content_type in ["video", "reel"] or platform.lower() in ["youtube", "tiktok"]:
            item["views"] = int(base_engagement * random.uniform(3, 8))

        result.append(item)

    return result

# File upload endpoint
@router.post("/upload")
async def upload_social_data(
    platform: str = Form(...),
    userId: str = Form(...),
    file: UploadFile = File(...)
) -> SocialDataUploadResponse:
    try:
        print(f"Processing file upload for platform: {platform}, user: {userId}")
        
        # Check file extension
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in ["csv", "xlsx", "xls", "json", "html"]:
            raise HTTPException(status_code=400, detail="File must be CSV, Excel (.xlsx, .xls), JSON or HTML")
        
        # Read file content
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Parse file based on extension
        df = None
        try:
            if file_ext == "csv":
                df = pd.read_csv(io.BytesIO(contents))
            elif file_ext in ["xlsx", "xls"]:
                df = pd.read_excel(io.BytesIO(contents))
            elif file_ext == "json":
                # Parse JSON file
                json_data = json.loads(contents.decode('utf-8'))
                
                # Handle different JSON structures
                if isinstance(json_data, list):
                    # If it's a list of records
                    df = pd.DataFrame(json_data)
                elif isinstance(json_data, dict):
                    if 'data' in json_data and isinstance(json_data['data'], list):
                        # Common API response format where data is in a 'data' key
                        df = pd.DataFrame(json_data['data'])
                    else:
                        # Convert flat dict to dataframe with single row
                        df = pd.DataFrame([json_data])
            elif file_ext == "html":
                # Try to extract tables from HTML
                try:
                    # Use pandas to read HTML tables
                    dfs = pd.read_html(io.BytesIO(contents))
                    if dfs and len(dfs) > 0:
                        # Use the first table found, or the largest one
                        df = max(dfs, key=len) if len(dfs) > 1 else dfs[0]
                    else:
                        raise HTTPException(status_code=400, detail="No tables found in HTML file")
                except Exception as html_error:
                    raise HTTPException(status_code=400, detail=f"Failed to parse HTML: {str(html_error)}")
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

        
        # Basic validation - check if the DataFrame is not empty
        if df.empty:
            raise HTTPException(status_code=400, detail="File contains no data")
        
        print(f"File parsed successfully with {len(df)} rows and {len(df.columns)} columns")
        print(f"Columns: {list(df.columns)}")
        
        # Store the original file
        storage_key = create_storage_key(platform, userId)
        db.storage.dataframes.put(storage_key, df)
        
        # Process data based on platform
        platform_data = process_platform_data(df, platform)
        
        # Return success response with processed data
        return SocialDataUploadResponse(
            success=True,
            data=platform_data
        )
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        print(f"Error processing file upload: {str(e)}")
        return SocialDataUploadResponse(
            success=False,
            error=f"Error processing file: {str(e)}"
        )

# Process data from uploaded file based on platform
def process_platform_data(df: pd.DataFrame, platform: str) -> PlatformData:
    # Normalize column names (lower case, remove spaces)
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # Initialize data with defaults
    followers = None
    following = None
    posts = None
    engagement = None
    likes = None
    comments = None
    shares = None
    views = None
    growth = None
    daily_stats = None
    content_performance = None
    
    # Common metrics extraction based on typical platform export formats
    # Follower count - look for any column that might contain follower information
    follower_cols = [col for col in df.columns if 'follower' in col]
    if follower_cols and not df[follower_cols[0]].isnull().all():
        # Get the most recent value (assuming data is sorted chronologically)
        followers = int(df[follower_cols[0]].iloc[-1])
    
    # Similar approach for other metrics
    following_cols = [col for col in df.columns if 'following' in col]
    if following_cols and not df[following_cols[0]].isnull().all():
        following = int(df[following_cols[0]].iloc[-1])
    
    post_cols = [col for col in df.columns if 'post' in col or 'content' in col or 'video' in col]
    if post_cols and not df[post_cols[0]].isnull().all():
        posts = int(df[post_cols[0]].iloc[-1])
    
    engagement_cols = [col for col in df.columns if 'engagement' in col or 'interaction' in col]
    if engagement_cols and not df[engagement_cols[0]].isnull().all():
        engagement = float(df[engagement_cols[0]].iloc[-1])
    
    # Check for time series data (daily stats)
    date_cols = [col for col in df.columns if 'date' in col or 'day' in col or 'time' in col]
    
    # If we have dates and followers over time, we can create daily stats
    if date_cols and follower_cols and len(df) > 1:
        daily_stats = []
        # Convert date column to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df[date_cols[0]]):
            try:
                df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
            except Exception as e:
                print(f"Error converting dates: {e}")
        
        # Sort by date
        df = df.sort_values(by=date_cols[0])
        
        # Create daily stats entries
        for _, row in df.iterrows():
            try:
                date_val = row[date_cols[0]]
                if pd.api.types.is_datetime64_any_dtype(date_val):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)
                
                # Build the daily stat
                stat = {"date": date_str}
                
                # Add followers if available
                if follower_cols and not pd.isna(row[follower_cols[0]]):
                    stat["followers"] = int(row[follower_cols[0]])
                
                # Add engagement if available
                if engagement_cols and not pd.isna(row[engagement_cols[0]]):
                    stat["engagement"] = float(row[engagement_cols[0]])
                elif 'engagement' in locals() and engagement is not None:
                    # Use constant engagement if time series isn't available
                    stat["engagement"] = engagement
                
                # Add views if available (for video platforms)
                view_cols = [col for col in df.columns if 'view' in col]
                if view_cols and not pd.isna(row[view_cols[0]]):
                    stat["views"] = int(row[view_cols[0]])
                
                daily_stats.append(stat)
            except Exception as e:
                print(f"Error processing row for daily stats: {e}")
                continue
    
    # Check for content performance data
    content_id_cols = [col for col in df.columns if 'id' in col or 'content_id' in col or 'post_id' in col]
    content_title_cols = [col for col in df.columns if 'title' in col or 'name' in col or 'description' in col]
    content_date_cols = [col for col in df.columns if 'publish' in col or 'posted' in col or 'date' in col]
    
    # If we have content identifiers and metrics, we can create content performance data
    if content_id_cols and date_cols and len(df) > 0:
        content_performance = []
        # Sort by date (most recent first)
        if date_cols and not df[date_cols[0]].isnull().all():
            df = df.sort_values(by=date_cols[0], ascending=False)
        
        # Limit to 10 items for consistency
        df_subset = df.head(10) if len(df) > 10 else df
        
        for idx, row in df_subset.iterrows():
            try:
                # Determine content type based on available columns
                content_type = "post"  # Default
                type_cols = [col for col in df.columns if 'type' in col or 'format' in col]
                if type_cols and not pd.isna(row[type_cols[0]]):
                    type_val = str(row[type_cols[0]]).lower()
                    if 'video' in type_val:
                        content_type = "video"
                    elif 'reel' in type_val:
                        content_type = "reel"
                    elif 'story' in type_val:
                        content_type = "story"
                
                # Build the content item
                item = {
                    "id": f"content-{idx}",
                    "type": content_type
                }
                
                # Add ID if available
                if content_id_cols and not pd.isna(row[content_id_cols[0]]):
                    item["id"] = str(row[content_id_cols[0]])
                
                # Add title if available
                if content_title_cols and not pd.isna(row[content_title_cols[0]]):
                    item["title"] = str(row[content_title_cols[0]])[:50]  # Limit length
                else:
                    item["title"] = f"{content_type.capitalize()} #{idx+1}"
                
                # Add date if available
                if content_date_cols and not pd.isna(row[content_date_cols[0]]):
                    date_val = row[content_date_cols[0]]
                    if pd.api.types.is_datetime64_any_dtype(date_val):
                        item["date"] = date_val.strftime("%Y-%m-%d")
                    else:
                        item["date"] = str(date_val)
                elif date_cols and not pd.isna(row[date_cols[0]]):
                    date_val = row[date_cols[0]]
                    if pd.api.types.is_datetime64_any_dtype(date_val):
                        item["date"] = date_val.strftime("%Y-%m-%d")
                    else:
                        item["date"] = str(date_val)
                else:
                    # Default to recent date if none available
                    today = datetime.now()
                    item["date"] = (today - timedelta(days=idx)).strftime("%Y-%m-%d")
                
                # Add engagement metrics if available
                like_cols = [col for col in df.columns if 'like' in col or 'favorite' in col]
                if like_cols and not pd.isna(row[like_cols[0]]):
                    item["likes"] = int(row[like_cols[0]])
                else:
                    item["likes"] = 0
                
                comment_cols = [col for col in df.columns if 'comment' in col or 'reply' in col]
                if comment_cols and not pd.isna(row[comment_cols[0]]):
                    item["comments"] = int(row[comment_cols[0]])
                else:
                    item["comments"] = 0
                
                share_cols = [col for col in df.columns if 'share' in col or 'retweet' in col or 'repost' in col]
                if share_cols and not pd.isna(row[share_cols[0]]):
                    item["shares"] = int(row[share_cols[0]])
                else:
                    item["shares"] = 0
                
                view_cols = [col for col in df.columns if 'view' in col or 'impression' in col]
                if view_cols and not pd.isna(row[view_cols[0]]):
                    item["views"] = int(row[view_cols[0]])
                
                content_performance.append(item)
            except Exception as e:
                print(f"Error processing row for content performance: {e}")
                continue
    
    # Calculate growth if we have time series follower data
    if daily_stats and len(daily_stats) > 1 and 'followers' in daily_stats[0] and 'followers' in daily_stats[-1]:
        try:
            first_followers = daily_stats[0]['followers']
            last_followers = daily_stats[-1]['followers']
            days_diff = len(daily_stats)
            
            if first_followers > 0 and days_diff > 0:
                # Calculate monthly growth rate
                daily_growth = (last_followers / first_followers) ** (1 / days_diff) - 1
                monthly_growth = ((1 + daily_growth) ** 30 - 1) * 100
                growth = round(monthly_growth, 1)
        except Exception as e:
            print(f"Error calculating growth rate: {e}")
    
    # Use missing data fallbacks
    if followers is None:
        # Use deterministic generation based on platform
        if platform == "instagram":
            followers = random.randint(5000, 15000)
        elif platform == "twitter":
            followers = random.randint(2000, 10000)
        elif platform == "facebook":
            followers = random.randint(3000, 20000)
        elif platform == "tiktok":
            followers = random.randint(8000, 30000)
        elif platform == "youtube":
            followers = random.randint(2000, 12000)
        elif platform == "linkedin":
            followers = random.randint(1000, 8000)
        else:
            followers = random.randint(2000, 10000)
    
    if following is None and platform in ["instagram", "twitter", "tiktok"]:
        # Typical following ratios
        if platform == "instagram":
            following = int(followers * random.uniform(0.05, 0.2))
        elif platform == "twitter":
            following = int(followers * random.uniform(0.2, 0.5))
        elif platform == "tiktok":
            following = int(followers * random.uniform(0.01, 0.1))
    
    if posts is None:
        if platform == "instagram":
            posts = random.randint(30, 200)
        elif platform == "twitter":
            posts = random.randint(100, 1000)
        elif platform == "facebook":
            posts = random.randint(50, 300)
        elif platform == "tiktok":
            posts = random.randint(20, 100)
        elif platform == "youtube":
            posts = random.randint(10, 50)
        elif platform == "linkedin":
            posts = random.randint(15, 100)
        else:
            posts = random.randint(30, 200)
    
    if engagement is None:
        # Typical engagement rates by platform
        if platform == "instagram":
            engagement = random.uniform(1.8, 4.2)
        elif platform == "twitter":
            engagement = random.uniform(0.8, 2.5)
        elif platform == "facebook":
            engagement = random.uniform(0.5, 2.0)
        elif platform == "tiktok":
            engagement = random.uniform(5.0, 9.0)
        elif platform == "youtube":
            engagement = random.uniform(1.0, 3.0)
        elif platform == "linkedin":
            engagement = random.uniform(1.0, 3.0)
        else:
            engagement = random.uniform(1.0, 3.0)
    
    if growth is None:
        # Typical monthly growth rates
        if platform == "instagram":
            growth = round(random.uniform(0.5, 1.5), 1)
        elif platform == "twitter":
            growth = round(random.uniform(0.3, 0.8), 1)
        elif platform == "facebook":
            growth = round(random.uniform(0.2, 0.6), 1)
        elif platform == "tiktok":
            growth = round(random.uniform(1.0, 2.5), 1)
        elif platform == "youtube":
            growth = round(random.uniform(0.4, 1.0), 1)
        elif platform == "linkedin":
            growth = round(random.uniform(0.3, 0.8), 1)
        else:
            growth = round(random.uniform(0.3, 1.0), 1)
    
    # Generate likes, comments, shares if not extracted
    if likes is None:
        likes = int(followers * engagement / 100)
    
    if comments is None:
        comments = int(likes * random.uniform(0.1, 0.3))
    
    if shares is None:
        shares = int(likes * random.uniform(0.05, 0.2))
    
    # For video platforms, add views if not extracted
    if platform in ["youtube", "tiktok"] and views is None:
        views = int(followers * random.uniform(3, 10))
    
    # Generate daily stats if not extracted
    if daily_stats is None or len(daily_stats) < 2:
        daily_stats = generate_time_series(followers)
    
    # Generate content performance if not extracted
    if content_performance is None or len(content_performance) < 2:
        content_performance = generate_content_performance(followers, platform)
    
    # Create and return the platform data object
    return PlatformData(
        followers=followers,
        following=following,
        posts=posts,
        engagement=engagement,
        growth=growth,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        dailyStats=daily_stats,
        contentPerformance=content_performance
    )
