from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
import databutton as db
import base64
from openai import OpenAI
import time
from io import BytesIO
import re

router = APIRouter()

# Initialize OpenAI client
openai_api_key = db.secrets.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

class ImageAnalysisResponse(BaseModel):
    analysis: str = Field(..., description="Analysis of the uploaded image")
    profile_data: Optional[Dict[str, Any]] = Field(None, description="Extracted profile data if image is a profile screenshot")

@router.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    try:
        # Read image data
        image_data = await file.read()
        
        # Ensure image is not too large (10MB limit)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size must be less than 10MB")
            
        # Convert to base64
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # Analyze image using OpenAI's Vision model
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are a social media PR specialist assistant that analyzes images.
                    When provided with an image, analyze it thoroughly in the context of social media performance and PR.
                    
                    If the image is a screenshot of a social media profile or post, extract and analyze metrics like:
                    - Follower count
                    - Engagement rates
                    - Content type and quality
                    - Visual consistency and branding
                    - Bio effectiveness
                    - Posting frequency patterns
                    
                    If it's a regular image (like a photo or graphic):
                    - Evaluate its visual appeal for social media
                    - Assess its potential engagement based on current trends
                    - Suggest improvements for better social media performance
                    - Identify any potential PR risks or opportunities
                    
                    Provide a comprehensive but concise analysis that the user can apply to improve their social media presence.
                    Organize your response with clear sections and bullet points.
                    Use markdown formatting for better readability.
                    
                    If you can detect specific metrics like follower counts, engagement rates, etc., from a profile screenshot,
                    include those in a structured format at the end of your analysis."""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image for social media PR purposes and provide actionable insights:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=1200
        )
        
        analysis = response.choices[0].message.content
        
        # Try to extract profile data if image is a screenshot
        profile_data = extract_profile_data(analysis)
        
        return ImageAnalysisResponse(
            analysis=analysis,
            profile_data=profile_data
        )
        
    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_profile_data(analysis_text: str) -> Optional[Dict[str, Any]]:
    """Extract structured profile data from the analysis text if possible"""
    try:
        # Look for common social media metrics in the text
        data = {}
        
        # Extract followers
        followers_match = re.search(r'([\d,]+)\s*followers', analysis_text, re.IGNORECASE)
        if followers_match:
            followers_text = followers_match.group(1).replace(',', '')
            data['followers'] = int(followers_text)
        
        # Extract following
        following_match = re.search(r'([\d,]+)\s*following', analysis_text, re.IGNORECASE)
        if following_match:
            following_text = following_match.group(1).replace(',', '')
            data['following'] = int(following_text)
        
        # Extract posts
        posts_match = re.search(r'([\d,]+)\s*posts', analysis_text, re.IGNORECASE)
        if posts_match:
            posts_text = posts_match.group(1).replace(',', '')
            data['posts'] = int(posts_text)
        
        # Extract engagement rate if mentioned
        engagement_match = re.search(r'([\d.]+)%?\s*engagement', analysis_text, re.IGNORECASE)
        if engagement_match:
            data['engagement'] = float(engagement_match.group(1))
        
        # Return None if we couldn't extract meaningful data
        return data if data else None
    except Exception as e:
        print(f"Error extracting profile data: {str(e)}")
        return None
