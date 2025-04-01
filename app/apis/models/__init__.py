from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime

class SocialPlatform(str, Enum):
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"

class SocialMediaProfile(BaseModel):
    platform: SocialPlatform
    username: Optional[str] = None
    profile_url: str
    followers: Optional[int] = None
    following: Optional[int] = None
    posts: Optional[int] = None
    engagement: Optional[float] = None
    growth: Optional[float] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    scrape_date: Optional[datetime] = None
    daily_stats: Optional[List[Dict[str, Any]]] = None
    content_performance: Optional[List[Dict[str, Any]]] = None
    raw_data: Optional[Dict[str, Any]] = None
