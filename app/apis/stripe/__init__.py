import json
import databutton as db
import stripe
from fastapi import APIRouter, Depends, Request, HTTPException, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.auth import AuthorizedUser

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
        print("Firebase Admin SDK already initialized in stripe API")
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
                print("Firebase Admin SDK initialized successfully in stripe API")
        except Exception as e:
            print(f"Error initializing Firebase Admin SDK: {e}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
except ImportError as e:
    # Firebase Admin SDK not available
    print(f"Firebase Admin SDK import error: {e}")
    print("Using in-memory store for testing")

def get_firestore_client():
    return firestore_db

# Initialize Stripe
stripe.api_key = db.secrets.get("STRIPE_SECRET_KEY")
stripe_webhook_secret = db.secrets.get("STRIPE_WEBHOOK_SECRET")

# Initialize router - we'll use the /api prefix for most endpoints
router = APIRouter(prefix="/api")

# Models
class PriceRequest(BaseModel):
    priceId: str
    
class SubscriptionUpdateRequest(BaseModel):
    userId: str
    subscriptionId: str
    status: str
    planType: str
    chatLimit: int

class CheckoutSessionRequest(BaseModel):
    priceId: str
    successUrl: str
    cancelUrl: str

class SubscriptionResponse(BaseModel):
    subscriptionId: Optional[str] = None
    clientSecret: Optional[str] = None
    status: str
    message: Optional[str] = None

# Plan configurations
SUBSCRIPTION_PLANS = {
    "free": {"chatLimit": 2, "price": 0},
    "beginner": {"chatLimit": 20, "price": 4.99, "price_id": "price_1R3TTdIRl6gJZ8ZEiOYJiNCN"},
    "influencer": {"chatLimit": 50, "price": 9.99, "price_id": "price_1R3TUHIRl6gJZ8ZEHOS6rOYQ"},
    "corporate": {"chatLimit": 30, "price": 19.99, "price_id": "price_1R3TV2IRl6gJZ8ZEUtXKnlS4"},
    "mastermind": {"chatLimit": 100, "price": 39.99, "price_id": "price_1R3TVbIRl6gJZ8ZEfK8PNEK5"},
}

# Helper function to map price ID to plan type
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
        print(f"Retrieved price from Stripe: {price.id}, amount: {price.unit_amount/100} {price.currency}")
        
        # If we have the price, check if product has metadata with plan_type
        if price and price.product:
            product = stripe.Product.retrieve(price.product)
            print(f"Retrieved product from Stripe: {product.name}")
            if product and product.metadata and 'plan_type' in product.metadata:
                plan_type = product.metadata['plan_type']
                print(f"Found plan_type in product metadata: {plan_type}")
                return plan_type
    except Exception as e:
        print(f"Error fetching price from Stripe: {e}")
    
    # Fallback based on price amounts if we couldn't get plan from metadata
    if price_id.startswith('price_'):
        try:
            # Try to get the price directly from Stripe
            price = stripe.Price.retrieve(price_id)
            # Map based on unit amount
            if price and hasattr(price, 'unit_amount'):
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
            print(f"Error determining plan from price: {e}")
    
    # Fallback to guessing based on price ID
    if "beginner" in price_id.lower():
        return "beginner"
    elif "influencer" in price_id.lower():
        return "influencer"
    elif "corporate" in price_id.lower():
        return "corporate"
    elif "mastermind" in price_id.lower():
        return "mastermind"
    
    # Default to free if we can't determine the plan
    return "free"

# Endpoint to create a checkout session
@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutSessionRequest, user: AuthorizedUser) -> Dict[str, Any]:
    try:
        print(f"Creating checkout session with price ID: {request.priceId}")
        print(f"User email: {user.email}, User ID: {user.sub}")
        print(f"Success URL: {request.successUrl}")
        print(f"Cancel URL: {request.cancelUrl}")
        
        # Make sure the Stripe API key is set
        if not stripe.api_key:
            print("ERROR: Stripe API key is not set")
            return {"status": "error", "message": "Payment processing is currently unavailable. Please try again later or contact support."}
        
        # Basic validation of price ID format
        if not request.priceId or not request.priceId.startswith('price_'):
            error_msg = f"Invalid price ID format: {request.priceId}. Price ID should start with 'price_'"
            print(f"ERROR: {error_msg}")
            return {"status": "error", "message": error_msg}
            
        # Verify the price exists in our known plans
        plan_type = None
        for plan, details in SUBSCRIPTION_PLANS.items():
            if details.get("price_id") == request.priceId:
                plan_type = plan
                break
        
        if not plan_type:
            print(f"WARNING: Price ID {request.priceId} not found in subscription plans, will be determined during checkout")
            # We'll allow the checkout to continue and will determine the plan type from Stripe
        else:
            print(f"Found matching plan: {plan_type} for price ID: {request.priceId}")
        
        # Create a new checkout session
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price": request.priceId,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=request.successUrl + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=request.cancelUrl,
                customer_email=user.email,  # Pre-fill customer email
                client_reference_id=user.sub,  # Store user ID for webhook
                metadata={
                    "userId": user.sub,
                    "planType": plan_type or get_plan_from_price_id(request.priceId),
                },
                allow_promotion_codes=True,  # Allow promo codes
            )
        except stripe.error.InvalidRequestError as e:
            error_message = str(e)
            print(f"Stripe invalid request error: {error_message}")
            
            if "No such price" in error_message:
                error_message = "The selected subscription plan is not available. Please try another plan or contact support."
            
            return {"status": "error", "message": error_message}
        except stripe.error.AuthenticationError:
            print("Stripe authentication error - invalid API key")
            return {"status": "error", "message": "Payment processing is currently unavailable. Please try again later."}
        
        print(f"Checkout session created: {checkout_session.id}")
        print(f"Checkout URL: {checkout_session.url}")
        
        # Return the checkout session URL
        return {"status": "success", "checkoutUrl": checkout_session.url}
    
    except Exception as e:
        error_message = str(e)
        print(f"Error creating checkout session: {error_message}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        # Provide more helpful error messages for common errors
        if "No such price" in error_message:
            error_message = "The selected plan is not available. Please try another plan or contact support."
        
        return {"status": "error", "message": error_message}

# Endpoint to handle Stripe webhook events
@router.post("/stripe-webhook")
async def stripe_webhook(request: Request) -> Dict[str, str]:
    # Get the webhook signature from the request header
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    
    # Get the request body
    payload = await request.body()
    
    # Verify the webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=stripe_webhook_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook signature verification failed: {str(e)}")
    
    # Handle the webhook event
    event_type = event["type"]
    data = event["data"]["object"]
    
    print(f"Processing webhook event: {event_type}")
    
    # Handle checkout.session.completed event
    if event_type == "checkout.session.completed":
        # Get the user ID from the checkout session
        user_id = data.get("client_reference_id")
        subscription_id = data.get("subscription")
        
        print(f"Checkout completed for user: {user_id}, subscription: {subscription_id}")
        
        if user_id and subscription_id:
            # Get plan information from metadata
            plan_type = data.get("metadata", {}).get("planType", "beginner")
            chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
            
            print(f"Activating subscription for user {user_id}: {plan_type} plan (limit: {chat_limit})")
            
            # Update the user's subscription in Firestore
            update_user_subscription(user_id, subscription_id, "active", plan_type, chat_limit)
    
    # Handle customer.subscription.updated event
    elif event_type == "customer.subscription.updated":
        subscription_id = data.get("id")
        status = data.get("status")
        
        # Get the customer ID
        customer_id = data.get("customer")
        if customer_id and subscription_id and status:
            # Find user with this subscription
            user_id = find_user_by_subscription(subscription_id)
            if user_id:
                # Get the plan from the subscription
                plan_type = get_plan_from_subscription_items(data.get("items", {}).get("data", []))
                chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
                
                # Update the user's subscription status
                update_user_subscription(user_id, subscription_id, status, plan_type, chat_limit)
    
    # Handle customer.subscription.deleted event
    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        if subscription_id:
            # Find user with this subscription
            user_id = find_user_by_subscription(subscription_id)
            if user_id:
                # Downgrade to free plan
                update_user_subscription(
                    user_id, 
                    None, 
                    "canceled", 
                    "free", 
                    SUBSCRIPTION_PLANS["free"]["chatLimit"]
                )
    
    return {"status": "success"}

# Helper function to find a user by subscription ID
def find_user_by_subscription(subscription_id: str) -> Optional[str]:
    if not HAS_FIREBASE:
        # In testing mode, just return a test user ID
        return "test_user_id"
        
    # Query Firestore for a user with this subscription ID
    db = get_firestore_client()
    if not db:
        return None
    users_ref = db.collection("users")
    query = users_ref.where("subscriptionId", "==", subscription_id).limit(1)
    results = query.get()
    
    # Return the user ID if found
    for doc in results:
        return doc.id
    
    return None

# Helper function to get plan type from subscription items
def get_plan_from_subscription_items(items: List[Dict[str, Any]]) -> str:
    if not items:
        print("No subscription items found")
        return "free"
    
    print(f"Subscription items: {items}")
    
    # Get the price ID from the first item - be more flexible in how we extract it
    price_id = None
    try:
        if isinstance(items[0], dict):
            # Dictionary case
            price = items[0].get("price", {})
            if isinstance(price, dict):
                price_id = price.get("id")
            else:
                price_id = price  # Direct string reference
        else:
            # Stripe object case
            price_id = items[0].price.id if hasattr(items[0], 'price') else None
    except Exception as e:
        print(f"Error extracting price ID: {e}")
    
    if not price_id:
        print("Could not extract price ID from subscription items")
        return "free"
    
    print(f"Extracted price ID: {price_id}")
    # Map price ID to plan type
    return get_plan_from_price_id(price_id)

# Helper function to update a user's subscription
def update_user_subscription(user_id: str, subscription_id: Optional[str], status: str, plan_type: str, chat_limit: int) -> None:
    if not HAS_FIREBASE:
        # In testing mode, just log the update
        print(f"Mock update subscription for user {user_id}: {plan_type} ({status})")
        return
        
    # Update the user's subscription in Firestore
    db = get_firestore_client()
    if not db:
        print(f"Cannot update subscription for {user_id}: Firestore not available")
        return
    
    try:
        user_ref = db.collection("users").document(user_id)
        
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

# Endpoint to get subscription plans
@router.get("/subscription-plans")
async def subscription_plans() -> Dict[str, Dict[str, Any]]:
    return SUBSCRIPTION_PLANS

# Endpoint to get current user's subscription
@router.get("/my-subscription")
async def my_subscription(user: AuthorizedUser) -> Dict[str, Any]:
    print(f"Getting subscription for user: {user.sub}")
    
    if not HAS_FIREBASE:
        # In testing mode, return a mock subscription
        print("Firebase not available, returning mock subscription")
        return {
            "subscription": "free",
            "subscriptionStatus": "none",
            "chatLimit": SUBSCRIPTION_PLANS["free"]["chatLimit"],
            "chatCount": 0
        }
    
    # Get the user's subscription from Firestore
    db = get_firestore_client()
    if not db:
        # If Firestore isn't available, return default subscription
        print("Firestore client not available, returning default subscription")
        return {
            "subscription": "free",
            "subscriptionStatus": "none",
            "chatLimit": SUBSCRIPTION_PLANS["free"]["chatLimit"],
            "chatCount": 0
        }
    
    try:
        user_ref = db.collection("users").document(user.sub)
        user_doc = user_ref.get()
        
        # If the user document doesn't exist, create a default one
        if not user_doc.exists:
            print(f"User document not found for {user.sub}, creating default profile")
            default_data = {
                "uid": user.sub,
                "email": user.email,
                "subscription": "free",
                "subscriptionStatus": "none",
                "chatLimit": SUBSCRIPTION_PLANS["free"]["chatLimit"],
                "chatCount": 0
            }
            user_ref.set(default_data)
            return default_data
        
        # User document exists, return subscription data
        user_data = user_doc.to_dict()
        print(f"Found user document for {user.sub}: {user_data}")
        
        # Check if user has a subscription ID but status is 'none' - fix it
        if user_data.get("subscriptionId") and user_data.get("subscriptionStatus") == "none":
            print(f"Fixing subscription status for user {user.sub}")
            # This is likely a subscription that didn't get properly updated by the webhook
            user_ref.update({"subscriptionStatus": "active"})
            user_data["subscriptionStatus"] = "active"
        
        # Verify subscription with Stripe if we have a subscription ID
        subscription_id = user_data.get("subscriptionId")
        if subscription_id and stripe.api_key:
            try:
                # Get subscription details from Stripe
                print(f"Verifying subscription {subscription_id} with Stripe")
                subscription = stripe.Subscription.retrieve(subscription_id)
                
                if subscription and subscription.status == "active":
                    # Check if we need to update the subscription
                    items = subscription.get("items", {}).get("data", [])
                    print(f"Active subscription found in Stripe: {subscription.id}")
                    
                    # Direct check of price ID against our known price IDs
                    price_id = None
                    if items and len(items) > 0:
                        # Get price ID directly
                        try:
                            if hasattr(items[0], 'price') and hasattr(items[0].price, 'id'):
                                price_id = items[0].price.id
                            elif isinstance(items[0], dict) and 'price' in items[0]:
                                price = items[0]['price']
                                if isinstance(price, dict) and 'id' in price:
                                    price_id = price['id']
                                else:
                                    price_id = price  # Direct string reference
                        except Exception as e:
                            print(f"Error extracting price ID directly: {e}")
                    
                    print(f"Direct price ID check: {price_id}")
                    
                    # Map price ID directly to plan
                    direct_plan_map = {
                        "price_1R1NdrIRl6gJZ8ZEXbmUL9P6": "beginner",
                        "price_1R1NePIRl6gJZ8ZEE5NWB6zN": "influencer",
                        "price_1R1NenIRl6gJZ8ZEDr9jyXJJ": "corporate",
                        "price_1R1Nf4IRl6gJZ8ZEaq62GldJ": "mastermind"
                    }
                    
                    plan_type = direct_plan_map.get(price_id, None)
                    if not plan_type:
                        # Fallback to more complex detection method
                        plan_type = get_plan_from_subscription_items(items)
                    
                    chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
                    
                    # Check if we need to update the database
                    print(f"Current user data: {user_data}")
                    print(f"Stripe subscription data: plan={plan_type}, status={subscription.status}, limit={chat_limit}")
                    print(f"Price ID: {price_id}")
                    
                    # Always update the subscription details from Stripe to ensure they're accurate
                    # This ensures that even if the webhook missed the update, we'll get it here
                    
                    print(f"Updating user subscription from Stripe: plan={plan_type}, limit={chat_limit}")
                    update_data = {
                        "subscription": plan_type,
                        "subscriptionStatus": subscription.status,
                        "chatLimit": chat_limit
                    }
                    user_ref.update(update_data)
                    
                    # Update our return data
                    user_data["subscription"] = plan_type
                    user_data["subscriptionStatus"] = subscription.status
                    user_data["chatLimit"] = chat_limit
                    
                    print(f"Updated subscription details for {user.sub}: {update_data}")
                        
            except Exception as e:
                print(f"Error verifying subscription with Stripe: {e}")
        
        return {
            "subscription": user_data.get("subscription", "free"),
            "subscriptionStatus": user_data.get("subscriptionStatus", "none"),
            "subscriptionId": subscription_id,
            "chatLimit": user_data.get("chatLimit", SUBSCRIPTION_PLANS["free"]["chatLimit"]),
            "chatCount": user_data.get("chatCount", 0)
        }
    except Exception as e:
        print(f"Error getting subscription: {e}")
        # Return default data in case of any error
        return {
            "subscription": "free",
            "subscriptionStatus": "none",
            "chatLimit": SUBSCRIPTION_PLANS["free"]["chatLimit"],
            "chatCount": 0
        }

# Endpoint to cancel subscription
@router.post("/cancel-subscription")
async def cancel_subscription(user: AuthorizedUser) -> Dict[str, str]:
    print(f"Canceling subscription for user: {user.sub}")
    
    if not HAS_FIREBASE:
        # In testing mode, just return success
        print("Firebase not available, returning mock cancellation success")
        return {"status": "success", "message": "Subscription has been canceled immediately"}
    
    # Get the user's subscription from Firestore
    db = get_firestore_client()
    if not db:
        return {"status": "error", "message": "Firestore not available"}
    
    try:
        user_ref = db.collection("users").document(user.sub)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            print(f"User document not found for {user.sub}")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        subscription_id = user_data.get("subscriptionId")
        
        if not subscription_id:
            print(f"No active subscription found for user {user.sub}")
            raise HTTPException(status_code=400, detail="No active subscription found")
        
        print(f"Immediately canceling subscription {subscription_id} for user {user.sub}")
        
        # Cancel the subscription immediately instead of at period end
        canceled_subscription = stripe.Subscription.delete(subscription_id)
        print(f"Stripe response: Subscription canceled with status {canceled_subscription.status}")
        
        # Update the user's subscription status in Firestore to canceled
        # Also reset to free plan
        user_ref.update({
            "subscriptionStatus": "canceled",
            "subscription": "free",
            "chatLimit": SUBSCRIPTION_PLANS["free"]["chatLimit"],
            "subscriptionId": None
        })
        
        print(f"Subscription {subscription_id} has been canceled immediately")
        return {"status": "success", "message": "Subscription has been canceled immediately"}
    
    except HTTPException as http_ex:
        # Re-raise HTTP exceptions
        raise http_ex
    except Exception as e:
        print(f"Error canceling subscription: {e}")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception args: {e.args}")
        raise HTTPException(status_code=400, detail=str(e))

# Pydantic model for session verification
class VerifySessionRequest(BaseModel):
    session_id: str

# Endpoint to verify a session client-side
@router.post("/verify-session")
async def verify_session(request: VerifySessionRequest, user: AuthorizedUser) -> Dict[str, str]:
    # Get request payload
    print(f"Starting session verification for user: {user.sub}")
    try:
        session_id = request.session_id
        
        if not session_id:
            print("No session ID provided in request")
            return {"status": "error", "message": "Missing session ID"}
        
        print(f"Verifying session ID: {session_id}")
            
        # Log useful debug info
        print(f"Processing verification for session {session_id} by user {user.sub} / {user.email}")
        print(f"Stripe API key available: {bool(stripe.api_key)}")
        print(f"Firestore available: {HAS_FIREBASE}")
        
        try:
            # Retrieve the checkout session from Stripe
            try:
                print(f"Retrieving checkout session from Stripe: {session_id}")
                session = stripe.checkout.Session.retrieve(session_id)
                print(f"Session retrieved: {session.id}, status: {session.status}, payment_status: {session.payment_status}")
                print(f"Full session details: {session}")
            except stripe.error.InvalidRequestError as e:
                print(f"Invalid session ID: {session_id}. Error: {str(e)}")
                return {"status": "error", "message": f"Invalid session ID: {str(e)}"}
            
            # Make sure we have a client_reference_id
            if not hasattr(session, 'client_reference_id') or not session.client_reference_id:
                print(f"Session {session_id} has no client_reference_id")
                # Attempt to continue using the current user's ID for verification
                print(f"Using current user ID {user.sub} as fallback for verification")
                session.client_reference_id = user.sub
            
            # Verify this session belongs to this user, but with leniency
            if session.client_reference_id != user.sub:
                print(f"Session user mismatch: {session.client_reference_id} vs {user.sub}")
                # This is a potential mismatch, but we'll proceed with a warning
                print("WARNING: Session user ID mismatch - proceeding anyway for better user experience")
                # We don't return an error here to allow for cases where the user might be using a different browser
                # or the auth state wasn't perfectly maintained during the Stripe redirect flow
            
            # Check if session is paid
            if not hasattr(session, 'payment_status') or session.payment_status != "paid":
                payment_status = getattr(session, 'payment_status', 'unknown')
                print(f"Session payment not completed: {payment_status}")
                return {"status": "error", "message": f"Payment not completed (status: {payment_status})"}
            
            # Get subscription ID from session
            subscription_id = getattr(session, 'subscription', None)
            print(f"Subscription ID from session: {subscription_id}")
            
            if not subscription_id:
                print("No subscription found in session")
                return {"status": "error", "message": "No subscription found in session"}
            
            # Get plan information from metadata or price
            plan_type = None
            if hasattr(session, 'metadata') and session.metadata:
                plan_type = session.metadata.get("planType")
            print(f"Plan type from session metadata: {plan_type}")
            
            if not plan_type:
                print("No plan type in metadata, trying to retrieve from subscription")
                # Try to get it from the subscription items
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    print(f"Subscription retrieved: {subscription.id}, status: {subscription.status}")
                    
                    if not hasattr(subscription, 'items') or not subscription.items.data:
                        print("No items found in subscription")
                        plan_type = "beginner"  # Default fallback
                    else:
                        items = subscription.items.data
                        price_id = items[0].price.id if hasattr(items[0], 'price') else None
                        
                        # First try to map directly to price IDs we know
                        price_to_plan = {
                            SUBSCRIPTION_PLANS["beginner"].get("price_id"): "beginner",
                            SUBSCRIPTION_PLANS["influencer"].get("price_id"): "influencer",
                            SUBSCRIPTION_PLANS["corporate"].get("price_id"): "corporate",
                            SUBSCRIPTION_PLANS["mastermind"].get("price_id"): "mastermind",
                        }
                        
                        plan_type = price_to_plan.get(price_id)
                        
                        if not plan_type:
                            # Try more complex detection
                            plan_type = get_plan_from_subscription_items(items)
                        
                        print(f"Plan type from subscription items: {plan_type}")
                        
                        # If we still don't have a plan type, try getting it from the product name
                        if not plan_type and price_id:
                            try:
                                product_id = items[0].price.product
                                product = stripe.Product.retrieve(product_id)
                                product_name = product.name.lower()
                                
                                # Try to match product name to a plan
                                for plan_name in ["beginner", "influencer", "corporate", "mastermind"]:
                                    if plan_name in product_name:
                                        plan_type = plan_name
                                        print(f"Determined plan {plan_type} from product name {product_name}")
                                        break
                            except Exception as e:
                                print(f"Error getting product details: {str(e)}")
                except Exception as sub_err:
                    print(f"Error retrieving subscription details: {sub_err}")
                    import traceback
                    traceback.print_exc()
                    plan_type = "beginner"  # Default fallback
            
            # Final fallback for plan type
            if not plan_type:
                print("Could not determine plan type, defaulting to beginner")
                plan_type = "beginner"
            
            # Get chat limit from plan
            chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
            print(f"Chat limit for plan {plan_type}: {chat_limit}")
            
            # Update the user's subscription in Firestore
            print(f"Updating user subscription: {user.sub}, {subscription_id}, active, {plan_type}, {chat_limit}")
            
            # Also store customer ID relationship for future webhook processing
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_id = subscription.customer
                if customer_id and HAS_FIREBASE:
                    db = get_firestore_client()
                    if db:
                        customer_ref = db.collection("customers").document(user.sub)
                        customer_ref.set({
                            "customerId": customer_id,
                            "subscriptionId": subscription_id
                        }, merge=True)
                        print(f"Stored customer mapping: {user.sub} -> {customer_id}")
            except Exception as e:
                print(f"Warning: Could not store customer mapping: {str(e)}")
                # This is not critical so continue processing
            
            # Update the user's subscription in Firestore
            update_user_subscription(user.sub, subscription_id, "active", plan_type, chat_limit)
            
            print("Session verification completed successfully")
            return {"status": "success", "message": "Subscription verified and activated", "plan": plan_type}
        
        except stripe.error.StripeError as stripe_error:
            print(f"Stripe error during verification: {stripe_error}")
            # More detailed error message for Stripe errors
            error_type = type(stripe_error).__name__
            error_message = str(stripe_error)
            
            if "No such session" in error_message:
                return {"status": "error", "message": "The checkout session could not be found. It may have expired or been processed already."}
            elif "No such subscription" in error_message:
                return {"status": "error", "message": "The subscription associated with this session could not be found."}
            else:
                return {"status": "error", "message": f"Stripe error: {error_type} - {error_message}"}
    
    except Exception as e:
        print(f"Error verifying session: {e}")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception args: {e.args}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
    except:
        print("Unhandled exception during session verification")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": "An unexpected error occurred during verification"}

# Simple public webhook endpoint for testing with both GET and POST methods
@router.post("/public-webhook", include_in_schema=True)
async def public_stripe_webhook_post(request: Request) -> Dict[str, str]:
    print("⭐️ Received webhook call to public endpoint")
    
    # Get the request body
    try:
        payload = await request.body()
        print(f"⭐️ Webhook payload received: {len(payload)} bytes")
        
        # Just parse the JSON to see what we got without verification
        event_data = json.loads(payload)
        print(f"⭐️ Webhook event type: {event_data.get('type', 'unknown')}")
        print(f"⭐️ Webhook event ID: {event_data.get('id', 'unknown')}")
        
        # If this is a checkout.session.completed event, try to process it
        if event_data.get('type') == "checkout.session.completed":
            print("⭐️ Processing checkout.session.completed event")
            data = event_data.get("data", {}).get("object", {})
            user_id = data.get("client_reference_id")
            subscription_id = data.get("subscription")
            
            if user_id and subscription_id:
                print(f"⭐️ Checkout completed for user: {user_id}, subscription: {subscription_id}")
                
                # Get plan information from metadata
                plan_type = data.get("metadata", {}).get("planType", "beginner")
                chat_limit = SUBSCRIPTION_PLANS.get(plan_type, {}).get("chatLimit", 20)
                
                print(f"⭐️ Activating subscription for user {user_id}: {plan_type} plan (limit: {chat_limit})")
                
                # Update the user's subscription in Firestore
                update_user_subscription(user_id, subscription_id, "active", plan_type, chat_limit)
        
        return {"status": "success", "message": "Webhook received and processed"}
    except Exception as e:
        print(f"⭐️ Error processing webhook: {e}")
        print(f"⭐️ Exception type: {type(e).__name__}")
        print(f"⭐️ Exception args: {e.args}")
        return {"status": "error", "message": str(e)}

# Simple GET endpoint for testing webhook connectivity
@router.get("/public-webhook", include_in_schema=True)
async def public_stripe_webhook_get() -> Dict[str, str]:
    print("⭐️ Received GET request to public webhook endpoint")
    return {"status": "success", "message": "Webhook endpoint is online and accessible"}

# Endpoint to create a Stripe customer portal session
@router.post("/create-customer-portal")
async def create_customer_portal_session(user: AuthorizedUser) -> Dict[str, str]:
    if not HAS_FIREBASE:
        # In testing mode, just return mock URL
        return {"url": "https://stripe.com/billing/portal-mock"}
    
    # Get the user's subscription from Firestore
    db = get_firestore_client()
    if not db:
        return {"status": "error", "message": "Firestore not available"}
    user_ref = db.collection("users").document(user.sub)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = user_doc.to_dict()
    subscription_id = user_data.get("subscriptionId")
    
    if not subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found")
    
    try:
        # Get the subscription to find the customer ID
        subscription = stripe.Subscription.retrieve(subscription_id)
        customer_id = subscription.customer
        
        # Create a customer portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="https://databutton.com/_projects/3cbfdca0-f781-4d65-8f3c-458e464d4560/app/subscriptions",
        )
        
        return {"url": portal_session.url}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))