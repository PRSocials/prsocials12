import databutton as db
import re
from fastapi import APIRouter, HTTPException, Depends
from app.auth import AuthorizedUser

router = APIRouter(prefix="/api/chat")

# Helper function to sanitize storage key
def sanitize_storage_key(key: str) -> str:
    """Sanitize storage key to only allow alphanumeric and ._- symbols"""
    return re.sub(r'[^a-zA-Z0-9._-]', '', key)

@router.delete("/history")
async def clear_chat_history(user: AuthorizedUser):
    """Clear the chat history for the current user"""
    try:
        # Get storage key for user's chat history
        storage_key = sanitize_storage_key(f"chat_history_{user.sub}")
        
        # Clear history by saving an empty list
        db.storage.json.put(storage_key, [])
        
        return {"success": True, "message": "Chat history cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing chat history: {str(e)}")
