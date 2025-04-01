import json
import stripe
import databutton as db
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

# Initialize Stripe with the secret key
stripe.api_key = db.secrets.get("STRIPE_SECRET_KEY")
stripe_webhook_secret = db.secrets.get("STRIPE_WEBHOOK_SECRET")

# Create a router for public endpoints - this must be set to 'open' in auth settings
# The tags=['public'] is crucial to ensure the router is publicly accessible
router = APIRouter(tags=['public'])

# Plan configurations - same as in the regular stripe API
SUBSCRIPTION_PLANS = {
    "free": {"chatLimit": 2, "price": 0},
    "beginner": {"chatLimit": 20, "price": 4.99, "price_id": "price_1R3TTdIRl6gJZ8ZEiOYJiNCN"},
    "influencer": {"chatLimit": 50, "price": 9.99, "price_id": "price_1R3TUHIRl6gJZ8ZEHOS6rOYQ"},
    "corporate": {"chatLimit": 30, "price": 19.99, "price_id": "price_1R3TV2IRl6gJZ8ZEUtXKnlS4"},
    "mastermind": {"chatLimit": 100, "price": 39.99, "price_id": "price_1R3TVbIRl6gJZ8ZEfK8PNEK5"},
}

# Try to import Firebase Admin, fallback to direct Firestore import if available
HAS_FIREBASE = False
firestore_db = None

try:
    # Try to import the Firebase Admin SDK package
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    # Check if Firebase Admin SDK is already initialized
    try:
        firebase_admin.get_app()  # This will throw ValueError if not initialized
        HAS_FIREBASE = True
        firestore_db = firestore.client()
        print("Firebase Admin SDK already initialized in stripe_public_api")
    except ValueError:
        # Not initialized, initialize it
        try:
            # Get Firebase credentials from secrets
            firebase_credentials_json = db.secrets.get("FIREBASE_SERVICE_ACCOUNT")
            if not firebase_credentials_json:
                print("Firebase service account not found in secrets")
            else:
                # Parse the credentials JSON
                cred_dict = json.loads(firebase_credentials_json)
                cred = credentials.Certificate(cred_dict)
                # Initialize the app
                firebase_admin.initialize_app(cred)
                HAS_FIREBASE = True
                firestore_db = firestore.client()
                print("Firebase Admin SDK initialized successfully in stripe_public_api")
        except Exception as e:
            print(f"Error initializing Firebase Admin SDK: {e}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
except ImportError as e:
    # Firebase Admin SDK not available
    print(f"Firebase Admin SDK import error: {e}")
    print("Using in-memory store for testing")

# Helper function to get plan type from price ID
def get_plan_from_price_id(price_id: str) -> str:
    print(f"Looking for plan type for price ID: {price_id}")
    
    # First check our SUBSCRIPTION_PLANS for direct matches
    for plan_name, details in SUBSCRIPTION_PLANS.items():
        if details.get("price_id") == price_id:
            print(f"Found direct price ID match for plan: {plan_name}")
            return plan_name
    
    # If not found in our config, look up in Stripe
    try:
        # Try to fetch the price from Stripe
        price = stripe.Price.retrieve(price_id)
        
        # If we have the price, check if product has metadata with plan_type
        if price and price.product:
            product = stripe.Product.retrieve(price.product)
            if product and product.metadata and 'plan_type' in product.metadata:
                plan_type = product.metadata['plan_type']
                print(f"Found plan_type in product metadata: {plan_type}")
                return plan_type
            
            # Fallback based on price amounts
            if hasattr(price, 'unit_amount'):
                amount = price.unit_amount / 100  # Convert from cents to dollars
                
                # Map price to plan based on amount
                if amount <= 4.99:
                    return "beginner"
                elif amount <= 9.99:
                    return "influencer"
                elif amount <= 19.99:
                    return "corporate"
                elif amount <= 39.99:
                    return "mastermind"
    except Exception as e:
        print(f"Error fetching price from Stripe: {e}")
    
    # Default to free if we can't determine the plan
    return "free"

# Helper function to update a user's subscription in Firestore
def update_user_subscription(user_id: str, subscription_id: str, status: str, plan_type: str, chat_limit: int) -> None:
    if not HAS_FIREBASE:
        # In testing mode, just log the update
        print(f"Mock update subscription for user {user_id}: {plan_type} ({status})")
        return
        
    # Update the user's subscription in Firestore
    if not firestore_db:
        print(f"Cannot update subscription for {user_id}: Firestore not available")
        return
    
    try:
        user_ref = firestore_db.collection("users").document(user_id)
        
        # Check if the document exists first
        doc = user_ref.get()
        if not doc.exists:
            print(f"Creating new user document for {user_id}")
            # Create a new document with minimal fields
            initial_data = {
                "uid": user_id,
                "subscription": "free",
                "subscriptionStatus": "none",
                "chatCount": 0,
                "chatLimit": 2,  # Free tier default
            }
            user_ref.set(initial_data)
        
        # Now update with subscription details
        update_data = {
            "subscription": plan_type,
            "subscriptionStatus": status,
            "chatLimit": chat_limit,
        }
        
        if subscription_id:
            update_data["subscriptionId"] = subscription_id
        
        # Execute the update
        user_ref.update(update_data)
        
        # Verify the update by reading the document again
        updated_doc = user_ref.get()
        updated_data = updated_doc.to_dict()
        print(f"Updated subscription for user {user_id}: {plan_type} ({status})")
        print(f"Verification - Current data: {updated_data}")
    except Exception as e:
        print(f"Error updating subscription: {e}")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception args: {e.args}")

# Helper function to find a user by subscription ID
def find_user_by_subscription(subscription_id: str) -> str:
    if not HAS_FIREBASE:
        # In testing mode, just return a test user ID
        return "test_user_id"
        
    # Query Firestore for a user with this subscription ID
    if not firestore_db:
        return None
    
    try:
        users_ref = firestore_db.collection("users")
        query = users_ref.where("subscriptionId", "==", subscription_id).limit(1)
        results = query.get()
        
        # Return the user ID if found
        for doc in results:
            return doc.id
    except Exception as e:
        print(f"Error finding user by subscription: {e}")
    
    return None

# Public webhook endpoint for Stripe - accessible without authentication
@router.post("/plans")
async def public_subscription_plans() -> Dict[str, Dict[str, Any]]:
    """Public endpoint to get subscription plans without requiring authentication"""
    print("Accessed public subscription plans endpoint")
    return SUBSCRIPTION_PLANS

@router.post("/webhook")
async def public_stripe_webhook(request: Request) -> Dict[str, str]:
    """Public endpoint to handle Stripe webhook events without requiring authentication"""
    print("⭐️ PUBLIC WEBHOOK: Received webhook call")
    
    try:
        # Get the request body
        payload = await request.body()
        print(f"⭐️ PUBLIC WEBHOOK: Payload received: {len(payload)} bytes")
        
        # Get the webhook signature from the request header
        signature = request.headers.get("stripe-signature")
        print(f"⭐️ PUBLIC WEBHOOK: Signature header present: {bool(signature)}")
        
        # Initialize event to None
        event = None
        
        # Try to parse the event with signature verification if available
        if signature and stripe_webhook_secret:
            try:
                print("⭐️ PUBLIC WEBHOOK: Verifying signature with webhook secret")
                event = stripe.Webhook.construct_event(
                    payload=payload,
                    sig_header=signature,
                    secret=stripe_webhook_secret
                )
                print("⭐️ PUBLIC WEBHOOK: Signature verification successful")
            except Exception as e:
                print(f"⭐️ PUBLIC WEBHOOK: Signature verification failed: {str(e)}")
                # Continue with parsing the payload directly
        
        # If signature verification failed or wasn't attempted, parse payload as JSON
        if not event:
            try:
                print("⭐️ PUBLIC WEBHOOK: Parsing payload as JSON without signature verification")
                event_data = json.loads(payload)
                # Create a simplified event structure manually
                event = {
                    "type": event_data.get("type"),
                    "data": {
                        "object": event_data.get("data", {}).get("object", {})
                    }
                }
                print(f"⭐️ PUBLIC WEBHOOK: Parsed event type: {event['type']}")
            except json.JSONDecodeError as e:
                print(f"⭐️ PUBLIC WEBHOOK: JSON parsing error: {str(e)}")
                return {"status": "error", "message": "Invalid JSON payload"}
        
        # Handle the webhook event
        event_type = event["type"] if isinstance(event, dict) else event.type
        data = event["data"]["object"] if isinstance(event, dict) else event.data.object
        
        print(f"⭐️ PUBLIC WEBHOOK: Processing webhook event: {event_type}")
        
        # Handle checkout.session.completed event
        if event_type == "checkout.session.completed":
            print("⭐️ PUBLIC WEBHOOK: Processing checkout.session.completed event")
            # Get the user ID and subscription ID
            user_id = data.get("client_reference_id") if isinstance(data, dict) else data.client_reference_id
            subscription_id = data.get("subscription") if isinstance(data, dict) else data.subscription
            
            print(f"⭐️ PUBLIC WEBHOOK: User ID: {user_id}, Subscription ID: {subscription_id}")
            
            if user_id and subscription_id:
                # Get metadata from session
                if isinstance(data, dict):
                    metadata = data.get("metadata", {})
                    plan_type = metadata.get("planType")
                else:
                    metadata = data.metadata if hasattr(data, "metadata") else {}
                    plan_type = metadata.get("planType") if metadata else None
                
                print(f"⭐️ PUBLIC WEBHOOK: Plan type from metadata: {plan_type}")
                
                # If plan type isn't in metadata, try to determine from subscription
                if not plan_type:
                    print("⭐️ PUBLIC WEBHOOK: Plan type not found in metadata, will retrieve from subscription")
                    try:
                        # Get subscription details from Stripe
                        subscription = stripe.Subscription.retrieve(subscription_id)
                        items = subscription.items.data if hasattr(subscription, 'items') else []
                        
                        # Get price ID from first item
                        if items:
                            price = items[0].price if hasattr(items[0], 'price') else None
                            price_id = price.id if hasattr(price, 'id') else None
                            
                            if price_id:
                                plan_type = get_plan_from_price_id(price_id)
                                print(f"⭐️ PUBLIC WEBHOOK: Determined plan type from subscription: {plan_type}")
                    except Exception as e:
                        print(f"⭐️ PUBLIC WEBHOOK: Error getting subscription details: {str(e)}")
                        plan_type = "beginner"  # Default to beginner plan
                
                # Default to beginner if still no plan type
                if not plan_type:
                    plan_type = "beginner"
                
                # Get chat limit for the plan
                chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
                
                # Update the user's subscription in Firestore
                print(f"⭐️ PUBLIC WEBHOOK: Updating user {user_id} with plan {plan_type}, limit {chat_limit}")
                update_user_subscription(user_id, subscription_id, "active", plan_type, chat_limit)
        
        # Handle customer.subscription.updated event
        elif event_type == "customer.subscription.updated":
            print("⭐️ PUBLIC WEBHOOK: Processing customer.subscription.updated event")
            # Get subscription details
            subscription_id = data.get("id") if isinstance(data, dict) else data.id
            status = data.get("status") if isinstance(data, dict) else data.status
            
            print(f"⭐️ PUBLIC WEBHOOK: Subscription ID: {subscription_id}, Status: {status}")
            
            if subscription_id and status:
                # Find the user with this subscription
                user_id = find_user_by_subscription(subscription_id)
                print(f"⭐️ PUBLIC WEBHOOK: Found user for subscription: {user_id}")
                
                if user_id:
                    # Get subscription items to determine plan type
                    items_data = data.get("items", {}).get("data", []) if isinstance(data, dict) else []
                    if not items_data and hasattr(data, 'items') and hasattr(data.items, 'data'):
                        items_data = data.items.data
                    
                    # Get price ID from items
                    price_id = None
                    if items_data:
                        if isinstance(items_data[0], dict):
                            price = items_data[0].get("price", {})
                            price_id = price.get("id") if isinstance(price, dict) else price
                        elif hasattr(items_data[0], 'price') and hasattr(items_data[0].price, 'id'):
                            price_id = items_data[0].price.id
                    
                    # Determine plan type from price ID
                    if price_id:
                        plan_type = get_plan_from_price_id(price_id)
                        print(f"⭐️ PUBLIC WEBHOOK: Determined plan type from price: {plan_type}")
                    else:
                        plan_type = "beginner"  # Default
                        print("⭐️ PUBLIC WEBHOOK: Could not determine plan type, using default: beginner")
                    
                    # Get chat limit for the plan
                    chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
                    
                    # Update the user's subscription
                    print(f"⭐️ PUBLIC WEBHOOK: Updating user {user_id} with status {status}, plan {plan_type}")
                    update_user_subscription(user_id, subscription_id, status, plan_type, chat_limit)
        
        # Handle customer.subscription.deleted event
        elif event_type == "customer.subscription.deleted":
            print("⭐️ PUBLIC WEBHOOK: Processing customer.subscription.deleted event")
            # Get subscription ID
            subscription_id = data.get("id") if isinstance(data, dict) else data.id
            print(f"⭐️ PUBLIC WEBHOOK: Subscription ID: {subscription_id}")
            
            if subscription_id:
                # Find the user with this subscription
                user_id = find_user_by_subscription(subscription_id)
                print(f"⭐️ PUBLIC WEBHOOK: Found user for subscription: {user_id}")
                
                if user_id:
                    # Downgrade to free plan
                    print(f"⭐️ PUBLIC WEBHOOK: Downgrading user {user_id} to free plan")
                    update_user_subscription(
                        user_id, 
                        None,  # No subscription ID 
                        "canceled", 
                        "free", 
                        SUBSCRIPTION_PLANS["free"]["chatLimit"]
                    )
        
        # Log success and return
        print("⭐️ PUBLIC WEBHOOK: Successfully processed webhook event")
        return {"status": "success", "event_type": event_type}
    
    except Exception as e:
        # Log the error and return
        print(f"⭐️ PUBLIC WEBHOOK ERROR: {str(e)}")
        print(f"⭐️ PUBLIC WEBHOOK ERROR type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# Simple GET endpoint for testing
@router.get("/webhook")
async def public_stripe_webhook_get2() -> Dict[str, str]:
    """Public GET endpoint for testing webhook connectivity"""
    print("⭐️ PUBLIC WEBHOOK: Received GET test request")
    return {
        "status": "success", 
        "message": "Stripe public webhook endpoint is online and accessible",
        "instructions": "Send Stripe webhook events to this URL using POST"
    }
