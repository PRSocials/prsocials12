import json
import databutton as db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime
from app.auth import AuthorizedUser

# Initialize Firebase Admin SDK if not already initialized
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    firebase_admin_initialized = False
    firestore_db = None
    
    # Check if Firebase Admin is initialized
    try:
        app = firebase_admin.get_app()
        print("Firebase Admin SDK already initialized in user_profiles API")
        firebase_admin_initialized = True
    except ValueError:
        # Get Firebase service account from secrets
        try:
            firebase_sa = db.secrets.get("FIREBASE_SERVICE_ACCOUNT")
            if firebase_sa and firebase_sa.strip():
                try:
                    # If it's a JSON string, parse it
                    if firebase_sa.strip().startswith('{'): 
                        cred_dict = json.loads(firebase_sa)
                        cred = credentials.Certificate(cred_dict)
                    else:
                        # If it's a base64 string or other format, handle accordingly
                        print("Firebase service account is not in JSON format in user_profiles API")
                        raise ValueError("Firebase service account is not in JSON format")
                        
                    # Initialize the app with the credentials
                    firebase_admin.initialize_app(cred)
                    firebase_admin_initialized = True
                    print("Firebase Admin SDK initialized successfully in user_profiles API")
                except json.JSONDecodeError as e:
                    print(f"Error parsing Firebase service account JSON in user_profiles API: {e}")
                    print(f"First 10 chars of service account: {firebase_sa[:10]}...")
                except Exception as e:
                    print(f"Error initializing Firebase Admin SDK in user_profiles API: {e}")
            else:
                print("Firebase service account not found or empty in secrets")
        except Exception as e:
            print(f"Error accessing Firebase service account secret in user_profiles API: {e}")
    
    # Only get Firestore client if Firebase Admin SDK is initialized
    if firebase_admin_initialized:
        try:
            firestore_db = firestore.client()
            print("Firestore client initialized successfully in user_profiles API")
        except Exception as e:
            print(f"Error getting Firestore client in user_profiles API: {e}")
            firestore_db = None
except ImportError:
    print("Firebase Admin SDK not available for user_profiles API")
    firebase_admin = None
    firestore_db = None

# Initialize router
router = APIRouter(prefix="/api")

# Models
class UserProfile(BaseModel):
    uid: str
    name: Optional[str] = None
    email: str
    createdAt: str
    subscription: str = "free"
    subscriptionStatus: str = "none"
    subscriptionId: Optional[str] = None
    chatCount: int = 0
    chatLimit: int = 2

class UserProfileResponse(BaseModel):
    success: bool
    profile: Optional[UserProfile] = None
    message: Optional[str] = None
    
class UserListResponse(BaseModel):
    success: bool
    users: Optional[List[UserProfile]] = None
    message: Optional[str] = None

# Endpoint to create a user profile
@router.post("/create-user-profile2")
async def create_user_profile22(user: AuthorizedUser) -> UserProfileResponse:
    if not firebase_admin_initialized or not firestore_db:
        return UserProfileResponse(
            success=False,
            message="Firebase Admin SDK not available or not properly initialized"
        )
    
    try:
        user_data = {
            "uid": user.sub,
            "email": user.email,
            "name": user.name if hasattr(user, "name") else None,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "subscription": "free",
            "subscriptionStatus": "none",
            "chatCount": 0,
            "chatLimit": 2
        }
        
        # Check if user already exists
        doc_ref = firestore_db.collection("users").document(user.sub)
        doc = doc_ref.get()
        
        if doc.exists:
            return UserProfileResponse(
                success=True,
                message="User profile already exists"
            )
        
        # Create new user document
        doc_ref.set(user_data)
        
        # Return success response
        return UserProfileResponse(
            success=True,
            message="User profile created successfully"
        )
    
    except Exception as e:
        print(f"Error creating user profile: {e}")
        return UserProfileResponse(
            success=False,
            message=f"Error creating user profile: {str(e)}"
        )

# Endpoint to get a user profile
@router.get("/get-user-profile2")
async def get_user_profile22(user: AuthorizedUser) -> UserProfileResponse:
    if not firebase_admin_initialized or not firestore_db:
        return UserProfileResponse(
            success=False,
            message="Firebase Admin SDK not available or not properly initialized"
        )
    
    try:
        # Get user document from Firestore
        try:
            if firebase_admin_initialized and firestore_db:
                doc_ref = firestore_db.collection("users").document(user.sub)
                doc = doc_ref.get()
                
                if not doc.exists:
                    # Create user profile if it doesn't exist
                    result = await create_user_profile22(user)
                    if not result.success:
                        return result
                        
                    # Get the newly created profile
                    doc = doc_ref.get()
                
                user_data = doc.to_dict()
            else:
                # Fallback to a default profile if Firebase is not available
                user_data = {
                    "uid": user.sub,
                    "email": user.email,
                    "name": user.name if hasattr(user, "name") else None,
                    "createdAt": datetime.now().isoformat(),
                    "subscription": "free",
                    "subscriptionStatus": "none",
                    "chatCount": 0,
                    "chatLimit": 2
                }
                print(f"Firebase not available, returning default profile for user {user.sub}")
        except Exception as e:
            print(f"Error accessing Firestore, using default profile: {e}")
            # Provide a default profile in case of any error
            user_data = {
                "uid": user.sub,
                "email": user.email,
                "name": user.name if hasattr(user, "name") else None,
                "createdAt": datetime.now().isoformat(),
                "subscription": "free",
                "subscriptionStatus": "none",
                "chatCount": 0,
                "chatLimit": 2
            }
        
        # Convert Firestore timestamp to string if needed
        if "createdAt" in user_data and hasattr(user_data["createdAt"], "timestamp"):
            user_data["createdAt"] = user_data["createdAt"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        elif "createdAt" not in user_data:
            user_data["createdAt"] = datetime.now().isoformat()
            
        # Return user profile
        return UserProfileResponse(
            success=True,
            profile=UserProfile(**user_data)
        )
    
    except Exception as e:
        print(f"Error getting user profile: {e}")
        return UserProfileResponse(
            success=False,
            message=f"Error getting user profile: {str(e)}"
        )

# Endpoint to update a user profile
@router.post("/update-user-profile2")
async def update_user_profile22(profile: UserProfile, user: AuthorizedUser) -> UserProfileResponse:
    if not firebase_admin_initialized or not firestore_db:
        return UserProfileResponse(
            success=False,
            message="Firebase Admin SDK not available or not properly initialized"
        )
    
    # Ensure the user can only update their own profile
    if profile.uid != user.sub:
        raise HTTPException(status_code=403, detail="You can only update your own profile")
    
    try:
        # Get user document reference
        doc_ref = firestore_db.collection("users").document(user.sub)
        
        # Update the profile
        update_data = profile.dict(exclude={"uid", "createdAt"})
        doc_ref.update(update_data)
        
        return UserProfileResponse(
            success=True,
            message="Profile updated successfully"
        )
    
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return UserProfileResponse(
            success=False,
            message=f"Error updating user profile: {str(e)}"
        )

# Endpoint to list all users (admin only)
@router.get("/list-users2")
async def list_users22(user: AuthorizedUser) -> UserListResponse:
    if not firebase_admin_initialized or not firestore_db:
        return UserListResponse(
            success=False,
            message="Firebase Admin SDK not available or not properly initialized"
        )
    
    # TODO: Add admin authorization check
    
    try:
        # Get all users from Firestore
        users_ref = firestore_db.collection("users")
        users = users_ref.stream()
        
        # Convert to list of dicts
        user_list = []
        for user_doc in users:
            user_data = user_doc.to_dict()
            
            # Convert Firestore timestamp to string
            if "createdAt" in user_data and hasattr(user_data["createdAt"], "timestamp"):
                user_data["createdAt"] = user_data["createdAt"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                
            user_list.append(UserProfile(**user_data))
        
        return UserListResponse(success=True, users=user_list)
    
    except Exception as e:
        print(f"Error listing users: {e}")
        return UserListResponse(
            success=False,
            message=f"Error listing users: {str(e)}"
        )
