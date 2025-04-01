from fastapi import APIRouter, HTTPException
import aiohttp
import databutton as db
import json

router = APIRouter(prefix="/apify-diagnostic")

# Get API token from secrets
APIFY_API_TOKEN = db.secrets.get("APIFY_API_TOKEN")

@router.get("/full-diagnostic")
async def run_apify_diagnostic():
    """Test endpoint to diagnose Apify API connection issues"""
    try:
        async with aiohttp.ClientSession() as session:
            # First, check if the token is valid by getting user info
            user_url = f"https://api.apify.com/v2/users/me?token={APIFY_API_TOKEN}"
            print(f"Checking user info at: {user_url.replace(APIFY_API_TOKEN, '***')}")
            
            async with session.get(user_url) as response:
                status = response.status
                response_text = await response.text()
                print(f"User info status: {status}")
                print(f"User info response: {response_text}")
                
                if status != 200:
                    return {
                        "success": False,
                        "error": f"Failed to validate Apify token: HTTP {status}",
                        "response": response_text
                    }
                
                user_data = await response.json()
            
            # Next, list available actors
            actors_url = f"https://api.apify.com/v2/acts?token={APIFY_API_TOKEN}"
            print(f"Checking available actors at: {actors_url.replace(APIFY_API_TOKEN, '***')}")
            
            async with session.get(actors_url) as response:
                status = response.status
                response_text = await response.text()
                print(f"Actors list status: {status}")
                print(f"Actors list response: {response_text}")
                
                if status != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list actors: HTTP {status}",
                        "response": response_text
                    }
                
                actors_data = await response.json()
            
            # Finally, check a public Instagram scraper actor to see if it exists and is accessible
            insta_actor_url = f"https://api.apify.com/v2/acts/zuzka~instagram-profile-scraper?token={APIFY_API_TOKEN}"
            print(f"Checking Instagram scraper actor at: {insta_actor_url.replace(APIFY_API_TOKEN, '***')}")
            
            async with session.get(insta_actor_url) as response:
                status = response.status
                response_text = await response.text()
                print(f"Instagram actor status: {status}")
                print(f"Instagram actor response: {response_text}")
                
                insta_actor_accessible = status == 200
            
            return {
                "success": True,
                "user": user_data,
                "actors_count": len(actors_data.get("data", {}).get("items", [])),
                "instagram_actor_accessible": insta_actor_accessible,
                "apify_token_valid": True,
            }
                
    except Exception as e:
        print(f"Error checking Apify connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking Apify connection: {str(e)}")
