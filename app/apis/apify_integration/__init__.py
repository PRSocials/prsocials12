import aiohttp
import json
import asyncio
import time
import re
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter
import databutton as db
from app.apis.models import SocialPlatform, SocialMediaProfile

# Get Apify API token from secrets
APIFY_API_TOKEN = db.secrets.get("APIFY_API_TOKEN")

router = APIRouter(prefix="/apify")

class ScrapeUrlRequest(BaseModel):
    url: str

class ScrapeUrlResponse(BaseModel):
    success: bool
    message: str = None
    data: SocialMediaProfile = None

class ApifyConnectionResponse(BaseModel):
    connected: bool
    message: str
    api_token_configured: bool = None
    test_actor_available: bool = None

@router.get("/check-connection", response_model=ApifyConnectionResponse)
async def check_apify_connection():
    """Check if Apify API is available and perform a basic test scrape"""
    global APIFY_API_TOKEN
    
    # If API token is not available, it's not configured
    if not APIFY_API_TOKEN:
        return ApifyConnectionResponse(
            connected=False,
            message="Apify API token not configured. Please add APIFY_API_TOKEN to secrets.",
            api_token_configured=False
        )
    try:
        # Make a simple request to the Apify API
        async with aiohttp.ClientSession() as session:
            # Try multiple possible endpoint formats to ensure compatibility
            test_urls = [
                # Primary user endpoint
                f"https://api.apify.com/v2/user/me?token={APIFY_API_TOKEN}"
            ]
            
            for test_url in test_urls:
                print(f"Testing Apify URL: {test_url.replace(APIFY_API_TOKEN, '***')}")
                try:
                    async with session.get(test_url, timeout=10) as response:
                        print(f"Apify test connection status: {response.status}")
                        response_text = await response.text()
                        print(f"Response preview: {response_text[:100]}...")
                        
                        if response.status == 200:
                            return ApifyConnectionResponse(
                                connected=True,
                                message=f"Successfully connected to Apify API using endpoint: {test_url.replace(APIFY_API_TOKEN, '***')}",
                                api_token_configured=True,
                                test_actor_available=True
                            )
                except Exception as e:
                    print(f"Error with endpoint {test_url.replace(APIFY_API_TOKEN, '***')}: {str(e)}")
                    continue
            
            # If we get here, none of the endpoints worked
            return ApifyConnectionResponse(
                connected=False,
                message="Could not connect to any Apify API endpoint. Please check your API token and try again.",
                api_token_configured=False
            )
    except Exception as e:
        return ApifyConnectionResponse(
            connected=False,
            message=f"Unexpected error checking Apify connection: {str(e)}",
            api_token_configured=True
        )

# Helper to extract numbers from strings like "1.5M" or "10K"
def parse_count(text):
    if not text:
        return None

    text = str(text).strip().lower()

    # Remove commas
    text = text.replace(',', '')

    # Handle K, M, B suffixes
    if 'k' in text:
        return int(float(text.replace('k', '')) * 1000)
    if 'm' in text:
        return int(float(text.replace('m', '')) * 1000000)
    if 'b' in text:
        return int(float(text.replace('b', '')) * 1000000000)

    # Try to extract any numbers
    numbers = re.findall(r'\d+\.?\d*', text)
    if numbers:
        return int(float(numbers[0]))

    return None

# Detect platform from URL
def detect_platform_from_url(url):
    url = url.lower()

    if 'instagram.com' in url:
        return SocialPlatform.INSTAGRAM
    elif 'twitter.com' in url or 'x.com' in url:
        return SocialPlatform.TWITTER
    elif 'facebook.com' in url or 'fb.com' in url:
        return SocialPlatform.FACEBOOK
    elif 'tiktok.com' in url:
        return SocialPlatform.TIKTOK
    elif 'youtube.com' in url or 'youtu.be' in url:
        return SocialPlatform.YOUTUBE
    elif 'linkedin.com' in url:
        return SocialPlatform.LINKEDIN

    return None

# Extract username from URL
def extract_username_from_url(url, platform):
    if platform == SocialPlatform.INSTAGRAM:
        match = re.search(r'instagram\.com/([^/?]+)', url)
        return match.group(1) if match else None

    elif platform in [SocialPlatform.TWITTER]:
        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', url)
        return match.group(1) if match else None

    elif platform == SocialPlatform.FACEBOOK:
        match = re.search(r'facebook\.com/([^/?]+)', url)
        return match.group(1) if match else None

    elif platform == SocialPlatform.TIKTOK:
        match = re.search(r'tiktok\.com/@([^/?]+)', url)
        return match.group(1) if match else None

    elif platform == SocialPlatform.YOUTUBE:
        # YouTube has two formats: /user/username or /c/channelname or /@username
        match = re.search(r'youtube\.com/(?:user|c|@)/([^/?]+)', url) or re.search(r'youtube\.com/([^/?]+)', url)
        return match.group(1) if match else None

    elif platform == SocialPlatform.LINKEDIN:
        match = re.search(r'linkedin\.com/in/([^/?]+)', url)
        return match.group(1) if match else None

    return None

# Process raw data from Apify based on platform
def process_apify_data(raw_data, platform):
    result = {
        "platform": platform.value,
        "username": "",
        "profile_url": "",
        "followers": 0,
        "following": 0,
        "posts": 0,
        "scrape_date": datetime.now().isoformat(),
        "daily_stats": None,
        "content_performance": None
    }

    # Process based on platform
    if platform == SocialPlatform.INSTAGRAM:
        result["username"] = raw_data.get("username", "")
        result["profile_url"] = raw_data.get("url", "")
        result["followers"] = parse_count(raw_data.get("followersCount", 0))
        result["following"] = parse_count(raw_data.get("followsCount", 0))
        result["posts"] = parse_count(raw_data.get("postsCount", 0))
        result["display_name"] = raw_data.get("fullName", "")
        result["bio"] = raw_data.get("biography", "")
        result["profile_image"] = raw_data.get("profilePicUrl", "")

    elif platform == SocialPlatform.TWITTER:
        result["username"] = raw_data.get("username", "")
        result["profile_url"] = raw_data.get("url", "")
        result["followers"] = parse_count(raw_data.get("followersCount", 0))
        result["following"] = parse_count(raw_data.get("friendsCount", 0))
        result["posts"] = parse_count(raw_data.get("statusesCount", 0))
        result["display_name"] = raw_data.get("displayName", "")
        result["bio"] = raw_data.get("description", "")
        result["profile_image"] = raw_data.get("profileImageUrl", "")

    elif platform == SocialPlatform.FACEBOOK:
        result["username"] = raw_data.get("username", "")
        result["profile_url"] = raw_data.get("url", "")
        result["followers"] = parse_count(raw_data.get("followers", 0))
        result["display_name"] = raw_data.get("name", "")
        result["bio"] = raw_data.get("about", "")
        result["profile_image"] = raw_data.get("profilePic", "")

    elif platform == SocialPlatform.TIKTOK:
        result["username"] = raw_data.get("username", "")
        result["profile_url"] = raw_data.get("url", "")
        result["followers"] = parse_count(raw_data.get("followerCount", 0))
        result["following"] = parse_count(raw_data.get("followingCount", 0))
        result["posts"] = parse_count(raw_data.get("videoCount", 0))
        result["display_name"] = raw_data.get("nickname", "")
        result["bio"] = raw_data.get("signature", "")
        result["profile_image"] = raw_data.get("avatarMedium", "")

    elif platform == SocialPlatform.YOUTUBE:
        result["username"] = raw_data.get("title", "")
        result["profile_url"] = raw_data.get("url", "")
        result["followers"] = parse_count(raw_data.get("subscriberCount", 0))
        result["posts"] = parse_count(raw_data.get("videoCount", 0))
        result["display_name"] = raw_data.get("title", "")
        result["bio"] = raw_data.get("description", "")
        result["profile_image"] = raw_data.get("thumbnailUrl", "")

    return result

# Helper function to handle Apify response
async def process_json_response(response_text, platform):
    try:
        data = json.loads(response_text)
        print(f"Successfully parsed JSON response of type: {type(data).__name__}")
        
        # Handle empty data
        if data is None:
            raise Exception("Apify returned null response")
            
        # Extract items based on response structure
        items = []
        
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if 'data' in data:
                if isinstance(data['data'], dict):
                    items = [data['data']]
                elif isinstance(data['data'], list):
                    items = data['data']
            elif 'items' in data and isinstance(data['items'], list):
                items = data['items']
            else:
                items = [data]
        
        # Make sure we have valid data
        if not items or len(items) == 0:
            raise Exception("No data items found in Apify response")
        
        # Get the first item
        raw_data = items[0]
        print(f"Using first data item of size: {len(str(raw_data))} bytes")
        
        # Process the raw data into our standard format
        return process_apify_data(raw_data, platform)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON response from Apify: {str(e)}")
        raise Exception(f"Invalid JSON response from Apify: {str(e)}")
        
# Scrape profile with Apify - simplified and more robust
async def scrape_profile_with_apify(url, platform):
    print(f"Scraping {platform.value} profile from {url}")

    if not APIFY_API_TOKEN:
        raise Exception("Apify API token is not configured. Please add an API token in settings.")

    # Select appropriate Apify actor for platform
    actor_id = None
    if platform == SocialPlatform.INSTAGRAM:
        actor_id = "dSCLg0C3YEZ83HzYX"  # Instagram Profile Scraper
    elif platform == SocialPlatform.TWITTER:
        actor_id = "shu8hvrXbJbY3Eb9W"  # Twitter Scraper
    elif platform == SocialPlatform.FACEBOOK:
        actor_id = "C43dQxtEJcExnmQDb"  # Facebook Scraper
    elif platform == SocialPlatform.TIKTOK:
        actor_id = "Ht6vuYYeQxhP3s5oJ"  # TikTok Scraper
    elif platform == SocialPlatform.YOUTUBE:
        actor_id = "5VxZm3AYupnHMH4EK"  # YouTube Scraper
    elif platform == SocialPlatform.LINKEDIN:
        actor_id = "fAJCzM35OgNu2C76W"  # LinkedIn Scraper

    if not actor_id:
        raise Exception(f"No Apify actor available for platform {platform.value}")

    # Prepare URL for actor run - use direct actor ID
    apify_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_API_TOKEN}"
    print(f"Using Apify API URL: {apify_url.replace(APIFY_API_TOKEN, '***')}")
    
    # Prepare run input based on platform - no build parameter needed for direct actor calls
    run_input = {}
    username = extract_username_from_url(url, platform)
    
    # Now set the platform-specific parameters
    if platform == SocialPlatform.INSTAGRAM:
        run_input.update({
            "usernames": [username] if username else [url],
            "resultsLimit": 1,
            "proxy": {"useApifyProxy": True}
        })
    elif platform == SocialPlatform.TWITTER:
        run_input.update({
            "handles": [username] if username else [url],
            "maxItems": 1,
            "proxy": {"useApifyProxy": True}
        })
    elif platform == SocialPlatform.TIKTOK:
        run_input.update({
            "usernames": [username] if username else [url],
            "maxResults": 1,
            "proxy": {"useApifyProxy": True}
        })
    elif platform == SocialPlatform.YOUTUBE:
        run_input.update({
            "startUrls": [{"url": url}],
            "maxResults": 1,
            "proxy": {"useApifyProxy": True}
        })
    elif platform == SocialPlatform.FACEBOOK:
        run_input.update({
            "startUrls": [{"url": url}],
            "maxPagesPerQuery": 1,
            "proxy": {"useApifyProxy": True}
        })
    elif platform == SocialPlatform.LINKEDIN:
        run_input.update({
            "startUrls": [{"url": url}],
            "proxy": {"useApifyProxy": True}
        })

    print(f"Starting Apify actor {actor_id} with input: {run_input}")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            
            # Start the actor run
            async with session.post(apify_url, json=run_input, headers=headers) as response:
                print(f"Apify start run response status: {response.status}")
                response_text = await response.text()
                print(f"Response preview: {response_text[:100]}...")
                
                if response.status not in [200, 201]:
                    # First URL format failed, try another format
                    # Try the direct actor URL format without task/ path
                    alt_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync?token={APIFY_API_TOKEN}"
                    print(f"First URL format failed, trying direct actor URL: {alt_url.replace(APIFY_API_TOKEN, '***')}")
                    
                    async with session.post(alt_url, json=run_input, headers=headers) as alt_response:
                        print(f"Alternative URL response status: {alt_response.status}")
                        alt_text = await alt_response.text()
                        
                        if alt_response.status not in [200, 201]:
                            raise Exception(f"Apify API error with both URL formats: {response.status} - {response_text[:100]}")
                        
                        # Use the successful alternative response
                        response = alt_response
                        response_text = alt_text
                
                # Parse response to get run ID
                try:
                    run_data = json.loads(response_text)
                    run_id = run_data.get("id") or run_data.get("data", {}).get("id")
                    if not run_id:
                        raise Exception("No run ID returned from Apify API")
                    
                    print(f"Started Apify run with ID: {run_id}")
                    
                    # Poll for results with exponential backoff - use the correct formats
                    # Try different URL formats for polling
                    poll_urls = [
                        f"https://api.apify.com/v2/acts/runs/{run_id}/dataset/items?token={APIFY_API_TOKEN}",
                        f"https://api.apify.com/v2/acts/{actor_id}/runs/{run_id}/dataset/items?token={APIFY_API_TOKEN}"
                    ]
                    
                    max_attempts = 15  # More attempts for longer-running scrapes
                    for attempt in range(1, max_attempts + 1):
                        wait_time = 5 * attempt  # Increasing backoff
                        print(f"Waiting {wait_time} seconds before polling (attempt {attempt}/{max_attempts})...")
                        await asyncio.sleep(wait_time)
                        
                        # Try each polling URL format
                        for poll_url in poll_urls:
                            print(f"Polling URL: {poll_url.replace(APIFY_API_TOKEN, '***')}")
                            try:
                                async with session.get(poll_url) as poll_response:
                                    print(f"Poll response status: {poll_response.status}")
                                    
                                    if poll_response.status == 200:
                                        poll_text = await poll_response.text()
                                        if poll_text and poll_text.strip() and poll_text != "[]":
                                            print(f"Got data from polling, size: {len(poll_text)} bytes")
                                            return await process_json_response(poll_text, platform)
                                        else:
                                            print("Empty result, actor may still be running")
                                    elif poll_response.status == 404:
                                        print("Dataset not yet available with this URL format")
                                    else:
                                        print(f"Unexpected status from polling: {poll_response.status}")
                            except Exception as e:
                                print(f"Error during polling with URL {poll_url.replace(APIFY_API_TOKEN, '***')}: {str(e)}")
                    
                    # If we get here, all polling attempts failed
                    raise Exception(f"Timeout waiting for results from Apify actor {actor_id}")
                    
                except json.JSONDecodeError:
                    raise Exception(f"Invalid JSON response from Apify: {response_text[:100]}")
                    
    except Exception as e:
        print(f"Error using Apify API: {str(e)}")
        raise Exception(f"Error accessing {platform.value} profile: {str(e)}")

# Main scrape endpoint
@router.post("/scrape", response_model=ScrapeUrlResponse)
async def scrape_social_url(request: ScrapeUrlRequest):
    print(f"Processing scrape request for URL: {request.url}")
    url = request.url

    try:
        # Detect platform from URL
        platform = detect_platform_from_url(url)
        if not platform:
            return ScrapeUrlResponse(
                success=False,
                message="Could not detect social media platform from URL. Please provide a valid social media profile URL."
            )

        print(f"Detected platform: {platform.value}")
        
        # Perform the scraping with Apify
        profile_data = await scrape_profile_with_apify(url, platform)

        # Create the profile object
        profile = SocialMediaProfile(**profile_data)

        return ScrapeUrlResponse(
            success=True,
            message=f"Successfully retrieved {platform.value} profile data.",
            data=profile
        )

    except Exception as e:
        print(f"Error scraping profile: {str(e)}")
        error_msg = str(e)

        # Return a more user-friendly message based on the error
        if "funds" in error_msg or "credits" in error_msg:
            message = "Apify account does not have sufficient credits. Please add credits to your Apify account."
        elif "API error" in error_msg:
            message = "Error connecting to Apify API. Please check your API token."
        elif "Rate limit" in error_msg:
            message = "Rate limit exceeded. Please try again later."
        elif "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
            message = "Request timed out. The social media platform may be responding slowly. Please try again later."
        elif "No data" in error_msg:
            message = "Could not retrieve data from the social media profile. The profile may be private or not exist."
        else:
            message = f"Error retrieving profile data: {error_msg}"

        return ScrapeUrlResponse(
            success=False,
            message=message
        )