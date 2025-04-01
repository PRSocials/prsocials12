import databutton as db
import re
import json
import time
from datetime import datetime
from openai import OpenAI
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, cast
from app.auth import AuthorizedUser
import base64

# Initialize router
router = APIRouter(prefix="/api/chat")

# Initialize OpenAI client
api_key = db.secrets.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# OpenAI Assistant ID
ASSISTANT_ID = "asst_zH2gNmtHevHg3ioE282EvCpZ"

# Helper function to generate ISO formatted timestamp
def now_as_iso() -> str:
    """Generate current timestamp in ISO format"""
    return datetime.utcnow().isoformat() + "Z"

# Helper function to sanitize storage key
def sanitize_storage_key(key: str) -> str:
    """Sanitize storage key to only allow alphanumeric and ._- symbols"""
    return re.sub(r'[^a-zA-Z0-9._-]', '', key)

# Models for request and response
class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = False
    image_data: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    usage: Optional[Dict[str, int]] = None

class ChatHistoryResponse(BaseModel):
    history: List[Dict[str, Any]]
    usage: Dict[str, int]

# System prompt for PR context
def get_system_prompt(social_accounts: List[Dict[str, Any]]) -> str:
    base_prompt = """
You are a professional PR assistant for social media (PRSocials). Your goal is to help users improve their social media presence, engagement, and strategy.

As a PR specialist, you can help with:
- Social media strategy development
- Content creation advice
- Audience growth tactics
- Crisis management
- Brand positioning
- Analytics interpretation
- Campaign planning
- Engagement improvement strategies

Your tone should be professional, strategic, and action-oriented. Provide practical advice that users can implement immediately.

For every response:
1. Be concise and actionable
2. Provide context for your recommendations
3. If appropriate, structure your response with bullet points or numbered lists
4. When possible, include a quick win alongside longer-term strategies
5. IMPORTANT: Always reference the user's actual social media analytics data when providing recommendations
6. Analyze trends and patterns in their data to provide personalized insights

Use markdown formatting in your responses to enhance readability:
- Use **bold** for important points and key concepts
- Use *italics* for emphasis
- Use bullet points for lists of related items
- Use numbered lists for sequential steps or prioritized items
- Use ### for section headers when organizing longer responses
- Use `code formatting` for any technical terms or commands

Always maintain a focus on ethical PR practices and sustainable growth strategies.
"""
    
    # If there are no connected accounts, return the base prompt
    if not social_accounts:
        return base_prompt + "\n\nNote: The user has not connected any social media accounts. Encourage them to connect their accounts for more personalized advice."
    
    # Add information about connected accounts
    accounts_data = "\n\nThe user has connected the following social media accounts. Use this data to provide personalized advice:\n"
    
    for idx, account in enumerate(social_accounts):
        platform = account.get("platform", "unknown")
        username = account.get("username", "unknown")
        platform_data = account.get("platformData", {})
        
        accounts_data += f"\nAccount {idx+1}:\n"
        accounts_data += f"- Platform: {platform}\n"
        accounts_data += f"- Username: @{username}\n"
        
        # Add key metrics if available
        if platform_data:
            accounts_data += "- Key metrics:\n"
            if "followers" in platform_data:
                accounts_data += f"  * Followers: {platform_data['followers']}\n"
            if "following" in platform_data:
                accounts_data += f"  * Following: {platform_data['following']}\n"
            if "posts" in platform_data:
                accounts_data += f"  * Posts: {platform_data['posts']}\n"
            if "engagement" in platform_data:
                accounts_data += f"  * Engagement rate: {platform_data['engagement']}%\n"
            if "growth" in platform_data:
                accounts_data += f"  * Growth rate: {platform_data['growth']}%\n"
            
            # Include recent performance if available
            if "dailyStats" in platform_data and platform_data["dailyStats"]:
                recent_stats = platform_data["dailyStats"][-7:] if len(platform_data["dailyStats"]) > 7 else platform_data["dailyStats"]
                
                if recent_stats:
                    accounts_data += "- Recent performance (last 7 days):\n"
                    for day in recent_stats:
                        date = day.get("date", "")
                        followers = day.get("followers", 0)
                        engagement = day.get("engagement", 0)
                        accounts_data += f"  * {date}: {followers} followers, {engagement}% engagement\n"
            
            # Include top content if available
            if "contentPerformance" in platform_data and platform_data["contentPerformance"]:
                # Sort by engagement (likes + comments + shares)
                top_content = sorted(
                    platform_data["contentPerformance"],
                    key=lambda x: (x.get("likes", 0) + x.get("comments", 0) + x.get("shares", 0)),
                    reverse=True
                )[:3]  # Get top 3
                
                if top_content:
                    accounts_data += "- Top performing content:\n"
                    for content in top_content:
                        title = content.get("title", "Untitled")
                        content_type = content.get("type", "post")
                        likes = content.get("likes", 0)
                        comments = content.get("comments", 0)
                        shares = content.get("shares", 0)
                        date = content.get("date", "")
                        
                        accounts_data += f"  * {title} ({content_type}) on {date}: {likes} likes, {comments} comments, {shares} shares\n"
            
            # Include insights if available
            if "insights" in platform_data and platform_data["insights"]:
                insights = platform_data["insights"]
                accounts_data += "- Calculated insights:\n"
                
                # Engagement trend
                if "engagementTrend" in insights:
                    trend = insights["engagementTrend"]
                    direction = "increasing" if trend["direction"] == "up" else "decreasing"
                    accounts_data += f"  * Engagement is {direction} by {abs(trend['value']):.1f}% over {trend['period']}\n"
                
                # Follower growth
                if "followerGrowth" in insights:
                    growth = insights["followerGrowth"]
                    direction = "growing" if growth["direction"] == "up" else "shrinking"
                    accounts_data += f"  * Follower count is {direction} by {abs(growth['value']):.1f}% over {growth['period']}\n"
                
                # Best content type
                if "bestContentType" in insights:
                    best_type = insights["bestContentType"]
                    accounts_data += f"  * Best performing content type: {best_type['type']} with average engagement of {best_type['avgEngagement']:.1f}\n"
    
    # Add guidance for using the data
    accounts_data += "\n\nIMPORTANT INSTRUCTIONS FOR USING THIS DATA:\n"
    accounts_data += "1. ALWAYS analyze and reference this social media data when providing advice\n"
    accounts_data += "2. Point out specific trends, metrics, or patterns you notice in their data\n"
    accounts_data += "3. Make clear connections between your recommendations and their actual metrics\n"
    accounts_data += "4. Compare their performance to industry benchmarks where relevant\n"
    accounts_data += "5. Highlight areas of strength and opportunities for improvement based on their data\n"
    accounts_data += "6. When they ask about a specific account or platform, focus your analysis on that account's data\n"
    accounts_data += "7. Suggest specific content types or strategies based on what's working well in their data\n"
    accounts_data += "8. Always explain WHY you're making a recommendation based on their data\n"
    
    return base_prompt + accounts_data

# Helper function to increment user's chat count
async def increment_chat_count(user_id: str) -> None:
    try:
        # Get current user profile from Firestore
        from app.apis.firebase_admin import get_firestore
        db_client = get_firestore()
        user_ref = db_client.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            current_count = user_data.get("chatCount", 0)
            
            # Update chat count
            user_ref.update({
                "chatCount": current_count + 1
            })
    except Exception as e:
        print(f"Error updating chat count: {e}")
        # Continue even if firebase update fails
        pass

# Helper function to save chat history
async def save_chat_history(user_id: str, messages: List[Message]) -> None:
    try:
        # Save to storage
        storage_key = sanitize_storage_key(f"chat_history_{user_id}")
        
        # Get existing history or create new
        try:
            history = db.storage.json.get(storage_key, default=[])
        except Exception:
            history = []
            
        # Add new messages to history, keeping only the last 50 conversations
        # Each conversation is a user message followed by an assistant message
        history.append({"timestamp": now_as_iso(), "messages": [m.dict() for m in messages]})
        
        # Keep only the last 50 conversations
        if len(history) > 50:
            history = history[-50:]
            
        # Save updated history
        db.storage.json.put(storage_key, history)
    except Exception as e:
        print(f"Error saving chat history: {e}")
        # Continue even if history save fails
        pass

# Helper function to get user's connected social accounts
async def get_connected_accounts(user_id: str) -> List[Dict[str, Any]]:
    try:
        # Get user's connected social accounts from Firestore
        from app.apis.firebase_admin import get_firestore
        db_client = get_firestore()
        
        # Query social_accounts collection for accounts linked to the user
        accounts_ref = db_client.collection("social_accounts").where("userId", "==", user_id)
        accounts = []
        
        for doc in accounts_ref.stream():
            account_data = doc.to_dict()
            # Add additional analytics calculation and insight generation
            if "platformData" in account_data:
                # Calculate engagement trend from dailyStats if available
                if "dailyStats" in account_data["platformData"] and account_data["platformData"]["dailyStats"]:
                    stats = account_data["platformData"]["dailyStats"]
                    if len(stats) >= 2:
                        # Calculate trend over last 7 days or whatever is available
                        recent_stats = stats[-7:] if len(stats) > 7 else stats
                        first_engagement = recent_stats[0].get("engagement", 0)
                        last_engagement = recent_stats[-1].get("engagement", 0)
                        
                        # Add engagement trend insights
                        trend_pct = ((last_engagement - first_engagement) / (first_engagement or 1)) * 100
                        account_data["platformData"]["insights"] = account_data["platformData"].get("insights", {})
                        account_data["platformData"]["insights"]["engagementTrend"] = {
                            "value": trend_pct,
                            "direction": "up" if trend_pct > 0 else "down",
                            "period": f"{len(recent_stats)} days"
                        }
                        
                        # Calculate best performing content type if contentPerformance is available
                        if "contentPerformance" in account_data["platformData"] and account_data["platformData"]["contentPerformance"]:
                            content = account_data["platformData"]["contentPerformance"]
                            
                            # Group by content type
                            content_by_type = {}
                            for item in content:
                                content_type = item.get("type", "post")
                                if content_type not in content_by_type:
                                    content_by_type[content_type] = []
                                content_by_type[content_type].append(item)
                            
                            # Calculate average engagement by type
                            type_performance = {}
                            for content_type, items in content_by_type.items():
                                total_eng = sum([(item.get("likes", 0) + item.get("comments", 0) + item.get("shares", 0)) for item in items])
                                avg_eng = total_eng / len(items) if items else 0
                                type_performance[content_type] = avg_eng
                            
                            # Find best performing type
                            if type_performance:
                                best_type = max(type_performance.items(), key=lambda x: x[1])
                                account_data["platformData"]["insights"]["bestContentType"] = {
                                    "type": best_type[0],
                                    "avgEngagement": best_type[1]
                                }
                        
                        # Calculate best posting days/times if we have enough data
                        # (This would require timestamps for each post, which we don't have in this mock data)
                        
                        # Calculate follower growth rate
                        if len(recent_stats) >= 2:
                            first_followers = recent_stats[0].get("followers", 0)
                            last_followers = recent_stats[-1].get("followers", 0)
                            growth_pct = ((last_followers - first_followers) / (first_followers or 1)) * 100
                            account_data["platformData"]["insights"]["followerGrowth"] = {
                                "value": growth_pct,
                                "direction": "up" if growth_pct > 0 else "down",
                                "period": f"{len(recent_stats)} days"
                            }
            
            accounts.append(account_data)
            
        return accounts
    except Exception as e:
        print(f"Error fetching connected accounts: {e}")
        return []

# Helper function to get or create a thread for a user
async def get_or_create_thread(user_id: str) -> str:
    try:
        # Look up thread ID in storage
        storage_key = sanitize_storage_key(f"assistant_thread_{user_id}")
        
        try:
            thread_data = db.storage.json.get(storage_key)
            thread_id = thread_data.get("thread_id")
            
            # Verify thread exists
            client.beta.threads.retrieve(thread_id)
            return thread_id
        except Exception:
            # Create new thread if not found or invalid
            thread = client.beta.threads.create()
            
            # Store thread ID
            db.storage.json.put(storage_key, {"thread_id": thread.id, "created_at": now_as_iso()})
            return thread.id
    except Exception as e:
        print(f"Error with thread management: {e}")
        # Create a new thread as fallback
        thread = client.beta.threads.create()
        return thread.id

# Helper function to get user's chat usage
async def get_chat_usage(user_id: str) -> Dict[str, int]:
    try:
        # Get current user profile from Firestore
        from app.apis.firebase_admin import get_firestore
        db_client = get_firestore()
        user_ref = db_client.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return {
                "used": user_data.get("chatCount", 0),
                "limit": user_data.get("chatLimit", 2)  # Default to free tier limit
            }
        return {"used": 0, "limit": 2}  # Default values
    except Exception as e:
        print(f"Error fetching chat usage: {e}")
        return {"used": 0, "limit": 2}  # Default values

# Endpoint to get chat history
@router.get("/history")
async def get_chat_history(user: AuthorizedUser) -> ChatHistoryResponse:
    storage_key = sanitize_storage_key(f"chat_history_{user.sub}")
    
    try:
        # Get chat history
        history = db.storage.json.get(storage_key, default=[])
    except Exception:
        history = []
    
    # Get usage info
    usage = await get_chat_usage(user.sub)
    
    return ChatHistoryResponse(history=history, usage=usage)

# Endpoint to chat with the PR assistant
@router.post("/", tags=["stream"])
async def chat(request: ChatRequest, user: AuthorizedUser):
    # Get user's chat usage
    usage = await get_chat_usage(user.sub)
    
    # Check if user has reached their limit
    if usage["used"] >= usage["limit"]:
        raise HTTPException(status_code=402, detail="Chat limit reached. Please upgrade your subscription to continue chatting.")
        
    # If streaming is requested, use streaming response
    if request.stream:
        from fastapi.responses import StreamingResponse
        return StreamingResponse(stream_chat_response(request, user), media_type="text/plain")
    
    try:
        # Get or create thread for this user
        thread_id = await get_or_create_thread(user.sub)
        
        # Always get and provide social accounts info for better context awareness
        social_accounts = await get_connected_accounts(user.sub)
        
        # Add context information if accounts are connected
        if social_accounts:
            account_context = """IMPORTANT USER CONTEXT - I HAVE THESE ACCOUNTS:
"""
            
            for idx, account in enumerate(social_accounts):
                platform = account.get("platform", "unknown")
                username = account.get("username", "unknown")
                platform_data = account.get("platformData", {})
                
                account_context += f"\n{idx+1}. {platform.upper()} ACCOUNT: @{username}\n"
                
                # Add key metrics
                followers = platform_data.get("followers", "unknown")
                following = platform_data.get("following", "unknown")
                posts = platform_data.get("posts", "unknown")
                engagement = platform_data.get("engagement", "unknown")
                
                account_context += f"   - Followers: {followers}\n"
                if following != "unknown":
                    account_context += f"   - Following: {following}\n"
                account_context += f"   - Posts: {posts}\n"
                account_context += f"   - Engagement Rate: {engagement}%\n"
                
                # Add insights if available
                insights = platform_data.get("insights", {})
                if insights:
                    account_context += "\n   ANALYTICS INSIGHTS:\n"
                    
                    # Engagement trend
                    if "engagementTrend" in insights:
                        trend = insights["engagementTrend"]
                        account_context += f"   - Engagement trend: {trend['direction'].upper()} {abs(trend['value']):.1f}% over {trend['period']}\n"
                    
                    # Follower growth
                    if "followerGrowth" in insights:
                        growth = insights["followerGrowth"]
                        account_context += f"   - Follower growth: {growth['direction'].upper()} {abs(growth['value']):.1f}% over {growth['period']}\n"
                    
                    # Best content type
                    if "bestContentType" in insights:
                        best_type = insights["bestContentType"]
                        account_context += f"   - Best performing content type: {best_type['type'].upper()} with avg engagement of {best_type['avgEngagement']:.1f}\n"
                
                # Add recent performance summary if available
                if "dailyStats" in platform_data and platform_data["dailyStats"]:
                    account_context += "\n   RECENT PERFORMANCE:\n"
                    recent_stats = platform_data["dailyStats"][-3:] # Just show last 3 days to avoid too much text
                    for day in recent_stats:
                        date = day.get("date", "")
                        day_followers = day.get("followers", 0)
                        day_engagement = day.get("engagement", 0)
                        account_context += f"   - {date}: {day_followers} followers, {day_engagement}% engagement\n"
                
                # Add top content if available
                if "contentPerformance" in platform_data and platform_data["contentPerformance"]:
                    top_content = platform_data["contentPerformance"][:2]  # Just show top 2 to avoid too much text
                    if top_content:
                        account_context += "\n   TOP PERFORMING CONTENT:\n"
                        for content in top_content:
                            title = content.get("title", "Untitled")
                            content_type = content.get("type", "post")
                            likes = content.get("likes", 0)
                            comments = content.get("comments", 0)
                            shares = content.get("shares", 0)
                            date = content.get("date", "")
                            account_context += f"   - {title} ({content_type}) on {date}: {likes} likes, {comments} comments, {shares} shares\n"
            
            account_context += "\nWhen I ask about 'my account' or 'my username' or any details about my accounts, ALWAYS reference this specific information directly. Analyze this data to provide personalized advice."
            
            # Add account information as a system message at the beginning
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=f"USER'S CONNECTED ACCOUNT INFO (PLEASE DIRECTLY REFERENCE THIS DATA WHEN ASKED ABOUT ACCOUNTS):\n{account_context}"
            )
        
        # Add the user's message to the thread
        if request.image_data:
            # If there's an image, create a message with both text and image
            message_content = [
                {"type": "text", "text": request.messages[-1].content}
            ]
            
            # Add image content with specific instructions for social media analysis
            # Format as per OpenAI docs: https://platform.openai.com/docs/guides/vision
            # Process the image data to ensure proper formatting
            image_data = request.image_data.strip()
            
            # Format the image URL correctly for OpenAI API
            if image_data.startswith('data:image/'):
                image_url = image_data  # Already properly formatted
            else:
                # If it's just base64 data, add the proper prefix
                image_url = f"data:image/jpeg;base64,{image_data}"
                
            message_content.append({
                "type": "image_url", 
                "image_url": {"url": image_url}
            })
            
            # Create message with image analysis prompt
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message_content
            )
        else:
            # Just text message
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=request.messages[-1].content  # Just add the most recent message
            )
        
        # Run the assistant on the thread
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )
        
        # Poll for the run to complete
        max_wait = 60  # Maximum wait time in seconds
        start_time = time.time()
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            
            if run_status.status == "completed":
                break
            elif run_status.status in ["failed", "cancelled", "expired"]:
                raise HTTPException(status_code=500, detail=f"Assistant run failed with status: {run_status.status}")
            
            # Check if we've exceeded max wait time
            if time.time() - start_time > max_wait:
                raise HTTPException(status_code=504, detail="Assistant response timed out")
                
            # Wait briefly before polling again
            time.sleep(1)
        
        # Get the latest message from the assistant
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=1
        )
        
        # Extract the assistant's reply
        assistant_message = messages.data[0]
        if assistant_message.role != "assistant":
            raise HTTPException(status_code=500, detail="Expected assistant reply but got something else")
            
        reply = ""
        for content_part in assistant_message.content:
            if content_part.type == "text":
                reply += content_part.text.value
        
        # Save this interaction to history for compatibility
        all_messages = request.messages.copy()
        all_messages.append(Message(role="assistant", content=reply))
        await save_chat_history(user.sub, all_messages)
        
        # Increment user's chat count
        await increment_chat_count(user.sub)
        
        return ChatResponse(reply=reply, usage=None)  # We don't get token usage from Assistant API
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error using OpenAI Assistant: {str(e)}")

# Helper function to process the last message for potential image inclusion
def process_last_message(message: Message, image_data: Optional[str]) -> Dict:
    """Process the last message to include image data if present"""
    # If no image data, just return the message as is
    if not image_data:
        return {"role": message.role, "content": message.content}
    
    # Process the image data
    image_data = image_data.strip()
    
    # Format the image URL correctly for OpenAI API
    # If it already has the data:image prefix, use it as is, otherwise add it
    if image_data.startswith('data:image/'):
        image_url = image_data  # Already properly formatted
    else:
        # If it's just base64 data, add the proper prefix
        image_url = f"data:image/jpeg;base64,{image_data}"
    
    # Return a multimodal message
    return {
        "role": message.role,
        "content": [
            {"type": "text", "text": message.content},
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": "high"
                }
            }
        ]
    }

# Helper function to stream chat response
async def stream_chat_response(request: ChatRequest, user: AuthorizedUser):
    try:
        # Process image generation requests directly in the chat
        if request.messages and request.messages[-1].role == "user":
            message_text = request.messages[-1].content.strip().lower()
            generate_match = re.match(r'^generate\s+(.+)$', message_text, re.IGNORECASE)
            
            if generate_match:
                prompt = generate_match.group(1).strip()
                yield "I'll generate an image for you based on your prompt. This may take a moment..."
                
                try:
                    # Generate image using OpenAI's DALL-E
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=prompt,
                        n=1,
                        size="1024x1024",
                        style="vivid",
                        quality="standard"
                    )
                    
                    # Get the image URL
                    image_url = response.data[0].url
                    
                    # Respond with the image URL in markdown format
                    yield f"\nHere's the image I generated based on your prompt:\n\n![Generated image]({image_url})\n\nIs there anything specific about this image you'd like me to explain or any changes you'd like to make?"
                    
                    # Save message to history
                    all_messages = request.messages.copy()
                    all_messages.append(Message(role="assistant", content=f"Here's the image I generated based on your prompt:\n\n![Generated image]({image_url})\n\nIs there anything specific about this image you'd like me to explain or any changes you'd like to make?"))
                    await save_chat_history(user.sub, all_messages)
                    
                    # Increment chat count
                    await increment_chat_count(user.sub)
                    return
                    
                except Exception as e:
                    print(f"Error generating image: {e}")
                    yield f"\nI'm sorry, I couldn't generate that image. {str(e)}"
                    return
        
        # If we get here, proceed with regular chat processing
        # Always get and provide social accounts info for better context awareness
        social_accounts = await get_connected_accounts(user.sub)
        
        # Start with the OpenAI chat completion API
        completion = client.chat.completions.create(
            model="gpt-4o",  # Using gpt-4o which has built-in vision capabilities
            messages=[
                {"role": "system", "content": get_system_prompt(social_accounts)},
                *[{"role": m.role, "content": m.content} for m in request.messages[:-1]],
                # Special handling for the last message which might include an image
                process_last_message(request.messages[-1], request.image_data)
            ],
            stream=True,
            max_tokens=800,
        )
        
        # Stream the response
        accumulated_response = ""
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                accumulated_response += content
                yield content
        
        # Save to chat history
        all_messages = request.messages.copy()
        all_messages.append(Message(role="assistant", content=accumulated_response))
        await save_chat_history(user.sub, all_messages)
        
        # Increment user's chat count
        await increment_chat_count(user.sub)
    
    except Exception as e:
        error_message = f"Error in chat: {str(e)}"
        print(error_message)
        yield error_message
        return
        thread_id = await get_or_create_thread(user.sub)
        
        # Always get and provide social accounts info for better context awareness
        social_accounts = await get_connected_accounts(user.sub)
        
        # Add context information if accounts are connected
        if social_accounts:
            account_context = """IMPORTANT USER CONTEXT - I HAVE THESE ACCOUNTS:
"""
            
            for idx, account in enumerate(social_accounts):
                platform = account.get("platform", "unknown")
                username = account.get("username", "unknown")
                platform_data = account.get("platformData", {})
                
                account_context += f"\n{idx+1}. {platform.upper()} ACCOUNT: @{username}\n"
                
                # Add key metrics
                followers = platform_data.get("followers", "unknown")
                following = platform_data.get("following", "unknown")
                posts = platform_data.get("posts", "unknown")
                engagement = platform_data.get("engagement", "unknown")
                
                account_context += f"   - Followers: {followers}\n"
                if following != "unknown":
                    account_context += f"   - Following: {following}\n"
                account_context += f"   - Posts: {posts}\n"
                account_context += f"   - Engagement Rate: {engagement}%\n"
                
                # Add insights if available
                insights = platform_data.get("insights", {})
                if insights:
                    account_context += "\n   ANALYTICS INSIGHTS:\n"
                    
                    # Engagement trend
                    if "engagementTrend" in insights:
                        trend = insights["engagementTrend"]
                        account_context += f"   - Engagement trend: {trend['direction'].upper()} {abs(trend['value']):.1f}% over {trend['period']}\n"
                    
                    # Follower growth
                    if "followerGrowth" in insights:
                        growth = insights["followerGrowth"]
                        account_context += f"   - Follower growth: {growth['direction'].upper()} {abs(growth['value']):.1f}% over {growth['period']}\n"
                    
                    # Best content type
                    if "bestContentType" in insights:
                        best_type = insights["bestContentType"]
                        account_context += f"   - Best performing content type: {best_type['type'].upper()} with avg engagement of {best_type['avgEngagement']:.1f}\n"
                
                # Add recent performance summary if available
                if "dailyStats" in platform_data and platform_data["dailyStats"]:
                    account_context += "\n   RECENT PERFORMANCE:\n"
                    recent_stats = platform_data["dailyStats"][-3:] # Just show last 3 days to avoid too much text
                    for day in recent_stats:
                        date = day.get("date", "")
                        day_followers = day.get("followers", 0)
                        day_engagement = day.get("engagement", 0)
                        account_context += f"   - {date}: {day_followers} followers, {day_engagement}% engagement\n"
                
                # Add top content if available
                if "contentPerformance" in platform_data and platform_data["contentPerformance"]:
                    top_content = platform_data["contentPerformance"][:2]  # Just show top 2 to avoid too much text
                    if top_content:
                        account_context += "\n   TOP PERFORMING CONTENT:\n"
                        for content in top_content:
                            title = content.get("title", "Untitled")
                            content_type = content.get("type", "post")
                            likes = content.get("likes", 0)
                            comments = content.get("comments", 0)
                            shares = content.get("shares", 0)
                            date = content.get("date", "")
                            account_context += f"   - {title} ({content_type}) on {date}: {likes} likes, {comments} comments, {shares} shares\n"
            
            account_context += "\nWhen I ask about 'my account' or 'my username' or any details about my accounts, ALWAYS reference this specific information directly. Analyze this data to provide personalized advice."
            
            # Add account information as a system message at the beginning
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=f"USER'S CONNECTED ACCOUNT INFO (PLEASE DIRECTLY REFERENCE THIS DATA WHEN ASKED ABOUT ACCOUNTS):\n{account_context}"
            )
        
        # Add the user's message to the thread
        if request.image_data:
            # If there's an image, create a message with both text and image
            # Process the image data to ensure proper formatting
            image_data = request.image_data.strip()
            
            # Ensure the data doesn't already have the data:image prefix
            if image_data.startswith('data:'):
                image_url = image_data  # Already properly formatted
            else:
                image_url = f"data:image/jpeg;base64,{image_data}"
                
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=[
                    {"type": "text", "text": request.messages[-1].content},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            )
        else:
            # Just text message
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=request.messages[-1].content  # Just add the most recent message
            )
        
        # Run the assistant on the thread with standard (non-streaming) method
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )
        
        # Create the illusion of streaming by yielding small chunks with delays
        # This is a fallback since the OpenAI Assistant API streaming doesn't match our async for loop approach
        
        # Wait for run to complete while yielding status indicators
        max_wait = 60  # Maximum wait time in seconds
        start_time = time.time()
        run_completed = False
        
        # Removed thinking message and instead use text that prompts the user about image generation
        
        # Poll for completion while yielding progress indicators
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            
            if run_status.status == "completed":
                run_completed = True
                break
            elif run_status.status in ["failed", "cancelled", "expired"]:
                yield f"\nError: Assistant run failed with status: {run_status.status}"
                return
            
            # Check if we've exceeded max wait time
            if time.time() - start_time > max_wait:
                yield "\nError: Response timed out"
                return
                
            time.sleep(1)  # Wait briefly between polls
        
        if run_completed:
            # Get the message and stream it in small chunks
            messages = client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",
                limit=1
            )
            
            # Extract the assistant's reply
            assistant_message = messages.data[0]
            if assistant_message.role != "assistant":
                yield "\nError: Expected assistant reply but got something else"
                return
                
            # Get full message content
            full_content = ""
            for content_part in assistant_message.content:
                if content_part.type == "text":
                    full_content += content_part.text.value
            
            # Clear the "Thinking..." text
            yield "\r" + " " * 10 + "\r"  # Clear the line
            
            # Stream the content in small chunks to simulate typing
            chunk_size = 2  # Smaller chunks for more realistic typing effect
            for i in range(0, len(full_content), chunk_size):
                yield full_content[i:i+chunk_size]
                # Variable timing between chunks for natural typing effect
                time.sleep(0.02 + (0.01 * (i % 3)))  # Slight random variation
            
            # Save the message to history
            all_messages = request.messages.copy()
            all_messages.append(Message(role="assistant", content=full_content))
            await save_chat_history(user.sub, all_messages)
            
            # Increment chat count
            await increment_chat_count(user.sub)
        
    except Exception as e:
        print(f"Error in streaming response: {e}")
        yield f"Error: {str(e)}"