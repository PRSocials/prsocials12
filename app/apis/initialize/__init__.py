import json
import databutton as db

# Try to import Firebase Admin packages
HAS_FIREBASE = False
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_FIREBASE = True
except ImportError as e:
    print(f"Firebase Admin SDK import error: {e}")
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Required for all API modules
router = APIRouter()

def initialize_firebase_admin():
    """Initialize Firebase Admin SDK if not already initialized"""
    try:
        # Check if already initialized
        app = firebase_admin.get_app()
        print("Firebase Admin SDK already initialized")
        return True, app
    except ValueError:
        # Not initialized, try to initialize
        try:
            # Try to get Firebase credentials from secrets
            firebase_credentials_json = db.secrets.get("FIREBASE_SERVICE_ACCOUNT")
            if not firebase_credentials_json:
                print("Firebase service account not found in secrets")
                return False, None
                
            # Parse JSON string into dictionary
            cred_dict = json.loads(firebase_credentials_json)
            # Create temporary credentials file
            cred = credentials.Certificate(cred_dict)
            # Initialize the app
            app = firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully")
            return True, app
        except Exception as e:
            print(f"Error initializing Firebase Admin SDK: {e}")
            return False, None
            
def get_firestore_client():
    """Get Firestore client if Firebase Admin SDK is initialized"""
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting Firestore client: {e}")
        return None

# API endpoint to check Firebase connection
@router.get("/firebase-status")
async def initialize_firebase_status() -> Dict[str, Any]:
    """Check if Firebase Admin SDK is initialized"""
    is_initialized, app = initialize_firebase_admin()
    firestore_client = get_firestore_client() if is_initialized else None
    
    return {
        "status": "ok" if is_initialized else "error",
        "firebase_initialized": is_initialized,
        "firestore_available": firestore_client is not None,
        "message": "Firebase Admin SDK is ready" if is_initialized else "Firebase Admin SDK failed to initialize"
    }