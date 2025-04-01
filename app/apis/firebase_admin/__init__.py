import json
import databutton as db
import os
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Import Firebase Admin modules
try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
    HAS_FIREBASE_ADMIN = True
except ImportError:
    print("Firebase Admin SDK not available, please install it with pip")
    HAS_FIREBASE_ADMIN = False

# Initialize router (required for all API modules)
router = APIRouter()

# Define models for our API
class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    displayName: Optional[str] = None
    photoURL: Optional[str] = None
    subscription: Optional[str] = "free"
    chatCount: int = 0
    lastActivity: Optional[str] = None
    settings: Optional[Dict[str, Any]] = {}

class UserProfileRequest(BaseModel):
    uid: str
    email: Optional[str] = None
    displayName: Optional[str] = None
    photoURL: Optional[str] = None

# Initialize Firebase Admin
firebase_admin_initialized = False
firebase_app = None
firestore_db = None

try:
    import firebase_admin
    
    # Check if Firebase Admin SDK is already initialized
    try:
        firebase_app = firebase_admin.get_app()
        print("Firebase Admin SDK already initialized in firebase_admin API")
        firebase_admin_initialized = True
    except ValueError:
        # Not initialized, try to initialize
        try:
            # Try to get Firebase credentials from secrets
            firebase_credentials_json = db.secrets.get("FIREBASE_SERVICE_ACCOUNT")
            if firebase_credentials_json:
                # Parse JSON string into dictionary
                cred_dict = json.loads(firebase_credentials_json)
                # Create temporary credentials file
                cred = credentials.Certificate(cred_dict)
                # Initialize the app
                firebase_app = firebase_admin.initialize_app(cred)
                firebase_admin_initialized = True
                print("Firebase Admin SDK initialized successfully in firebase_admin API")
            else:
                print("Firebase service account not found in secrets")
        except Exception as e:
            print(f"Error initializing Firebase Admin SDK in firebase_admin API: {e}")
    
    # Only get Firestore client if Firebase Admin SDK is initialized
    if firebase_admin_initialized:
        try:
            firestore_db = firestore.client()
            print("Firestore client initialized successfully in firebase_admin API")
        except Exception as e:
            print(f"Error getting Firestore client in firebase_admin API: {e}")
            firestore_db = None
except ImportError:
    print("Firebase Admin SDK not available in firebase_admin API")

# Helper functions for Firebase operations
def get_auth():
    if firebase_admin_initialized:
        return auth
    return None

def get_firestore():
    return firestore_db

# API endpoints for user profiles using Firebase Admin SDK
@router.post("/create-user-profile")
async def create_user_profile(user_data: UserProfileRequest) -> Dict[str, Any]:
    """
    Create a new user profile in Firestore
    """
    try:
        # Create basic profile with default values
        profile = UserProfile(
            uid=user_data.uid,
            email=user_data.email,
            displayName=user_data.displayName,
            photoURL=user_data.photoURL,
            subscription="free",
            chatCount=0,
            lastActivity=None,
            settings={}
        )
        
        # Save profile to Firestore
        db = get_firestore()
        db.collection('users').document(user_data.uid).set(profile.dict())
        
        return {"success": True, "profile": profile.dict()}
    except Exception as e:
        print(f"Error creating user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user profile: {str(e)}"
        )

@router.get("/get-user-profile/{uid}")
async def get_user_profile(uid: str) -> Dict[str, Any]:
    """
    Get a user profile by UID from Firestore
    """
    try:
        db = get_firestore()
        doc_ref = db.collection('users').document(uid)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User profile not found for UID: {uid}"
            )
        
        return {"success": True, "profile": doc.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}"
        )

@router.put("/update-user-profile/{uid}")
async def update_user_profile(uid: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a user profile by UID in Firestore
    """
    try:
        db = get_firestore()
        doc_ref = db.collection('users').document(uid)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User profile not found for UID: {uid}"
            )
        
        # Update document with merge=True to only update specified fields
        doc_ref.update(update_data)
        
        # Get the updated document
        updated_doc = doc_ref.get()
        
        return {"success": True, "profile": updated_doc.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user profile: {str(e)}"
        )

@router.get("/list-users")
async def list_users(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    List all user profiles with pagination from Firestore
    Admin only endpoint
    """
    try:
        db = get_firestore()
        # Note: Firestore doesn't directly support offset pagination
        # For a production app, you'd want to use cursor-based pagination
        users_ref = db.collection('users').limit(limit)
        docs = users_ref.stream()
        
        user_profiles = [doc.to_dict() for doc in docs]
        
        # Simple client-side pagination
        total_count = len(user_profiles)
        paginated_profiles = user_profiles[offset:offset+limit] if offset < total_count else []
        
        return {
            "success": True, 
            "users": paginated_profiles,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        print(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )
