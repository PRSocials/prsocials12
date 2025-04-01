from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import databutton as db
import base64
from openai import OpenAI
import time

router = APIRouter()

class ImageGenerationRequest(BaseModel):
    prompt: str = Field(
        ..., 
        description="Detailed description of the image you want to generate"
    )
    n: int = Field(
        1, 
        description="Number of images to generate", 
        ge=1, 
        le=4
    )
    size: str = Field(
        "1024x1024", 
        description="Size of the image", 
        enum=["1024x1024", "1792x1024", "1024x1792"]
    )
    style: str = Field(
        "vivid", 
        description="Image style", 
        enum=["vivid", "natural"]
    )
    quality: str = Field(
        "standard", 
        description="Image quality", 
        enum=["standard", "hd"]
    )
    social_purpose: Optional[str] = Field(
        None,
        description="The social media purpose for this image (post, story, ad, etc.)"
    )
    brand_identity: Optional[str] = Field(
        None,
        description="Brand identity elements to include (colors, style, etc.)"
    )

class ImageGenerationResponse(BaseModel):
    image_urls: List[str] = Field(
        ..., 
        description="URLs of the generated images"
    )
    prompt: str = Field(
        ..., 
        description="The prompt that was used for generation"
    )
    enhanced_prompt: str = Field(
        ...,
        description="The PR-enhanced prompt that was used for generation"
    )

@router.post("/generate")
async def generate_image(request: ImageGenerationRequest) -> ImageGenerationResponse:
    try:
        # Initialize OpenAI client
        openai_api_key = db.secrets.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not found. Please configure it in settings.")
        
        client = OpenAI(api_key=openai_api_key)
        
        # Create an enhanced prompt for social media PR purposes
        enhanced_prompt = enhance_prompt_for_pr(request.prompt, request.social_purpose, request.brand_identity)
        
        # Call OpenAI API to generate images
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            n=request.n,
            size=request.size,
            quality=request.quality,
            style=request.style
        )
        
        # Extract image URLs
        image_urls = [image.url for image in response.data]
        
        return ImageGenerationResponse(
            image_urls=image_urls,
            prompt=request.prompt,
            enhanced_prompt=enhanced_prompt
        )
        
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def enhance_prompt_for_pr(base_prompt: str, social_purpose: Optional[str], brand_identity: Optional[str]) -> str:
    """Enhance the user's prompt to create better images for PR purposes"""
    enhanced_prompt = base_prompt
    
    # Add specific guidance based on social purpose
    if social_purpose:
        if social_purpose.lower() == "post":
            enhanced_prompt += ". This image should be visually striking with balanced composition, suitable for a high-engagement social media post."
        elif social_purpose.lower() == "story":
            enhanced_prompt += ". This image should have vertical composition, with focal points centered, ideal for social media stories."
        elif social_purpose.lower() == "ad":
            enhanced_prompt += ". This image should have attention-grabbing elements and clear focal points, designed for advertising purposes."
        elif social_purpose.lower() == "profile":
            enhanced_prompt += ". This image should work well as a profile picture, with clear subject focus and professional composition."
        else:
            enhanced_prompt += f". This image is intended for {social_purpose} on social media."
    else:
        # Default enhancement for social media content
        enhanced_prompt += ". Create an image optimized for social media engagement with vibrant visuals and clear composition."
    
    # Add brand identity guidance
    if brand_identity:
        enhanced_prompt += f" The style should align with this brand identity: {brand_identity}."
    
    # Always add these PR-focused improvements
    enhanced_prompt += " The image should be professional, visually appealing, and suitable for brand communication. Avoid controversial or potentially offensive elements."
    
    return enhanced_prompt
