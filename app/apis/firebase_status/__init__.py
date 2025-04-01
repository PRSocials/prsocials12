from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

# Import firebase_admin API to use its initialized services
from app.apis.firebase_admin import firebase_admin_initialized, get_auth, get_firestore

# Initialize router
router = APIRouter()

# Define response model
class FirebaseStatusResponse(BaseModel):
    initialized: bool
    auth_available: bool
    firestore_available: bool
    message: str

@router.get("/status", response_model=FirebaseStatusResponse)
async def check_firebase_status() -> FirebaseStatusResponse:
    """Check Firebase Admin SDK initialization status"""
    auth_client = get_auth()
    firestore_client = get_firestore()
    
    status_response = {
        "initialized": firebase_admin_initialized,
        "auth_available": auth_client is not None,
        "firestore_available": firestore_client is not None,
        "message": ""
    }
    
    if firebase_admin_initialized and auth_client and firestore_client:
        status_response["message"] = "Firebase Admin SDK is fully initialized and operational"
    elif not firebase_admin_initialized:
        status_response["message"] = "Firebase Admin SDK is not initialized"
    elif not auth_client:
        status_response["message"] = "Firebase Auth client is not available"
    elif not firestore_client:
        status_response["message"] = "Firestore client is not available"
    
    return FirebaseStatusResponse(**status_response)
