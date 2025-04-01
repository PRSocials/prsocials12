import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any

# Create a router with no prefix and ensure it's publicly accessible
# The tags=['public'] isn't enough, the auth config needs to be set to 'open' in Databutton UI
router = APIRouter(tags=['public'])

# NOTE TO USERS: This API must be set to 'open' in the Databutton auth settings
# Go to Settings > Authentication > APIs and set public_stripe_webhook to 'open'

# Public webhook endpoint accessible at /public-webhook with no authentication
@router.post("/public-webhook")
async def public_stripe_webhook_post2(request: Request) -> Dict[str, str]:
    print("⭐️ PUBLIC WEBHOOK: Received webhook call")
    
    # Get the request body
    try:
        payload = await request.body()
        print(f"⭐️ PUBLIC WEBHOOK: Payload received: {len(payload)} bytes")
        
        # Try to parse the JSON
        if payload:
            try:
                event_data = json.loads(payload)
                print(f"⭐️ PUBLIC WEBHOOK: Event type: {event_data.get('type', 'unknown')}")
                print(f"⭐️ PUBLIC WEBHOOK: Event ID: {event_data.get('id', 'unknown')}")
                
                # Print the full event for debugging
                print(f"⭐️ PUBLIC WEBHOOK: Full event: {event_data}")
                
                # If this is a checkout.session.completed event, log important details
                if event_data.get('type') == "checkout.session.completed":
                    session = event_data.get("data", {}).get("object", {})
                    print(f"⭐️ PUBLIC WEBHOOK: Checkout session completed: {session.get('id')}")
                    print(f"⭐️ PUBLIC WEBHOOK: User ID: {session.get('client_reference_id')}")
                    print(f"⭐️ PUBLIC WEBHOOK: Subscription ID: {session.get('subscription')}")
                    print(f"⭐️ PUBLIC WEBHOOK: Payment status: {session.get('payment_status')}")
                    print(f"⭐️ PUBLIC WEBHOOK: Full session: {session}")
                
                # If this is a subscription event, log important details
                if event_data.get('type').startswith("customer.subscription."):
                    subscription = event_data.get("data", {}).get("object", {})
                    print(f"⭐️ PUBLIC WEBHOOK: Subscription event: {event_data.get('type')}")
                    print(f"⭐️ PUBLIC WEBHOOK: Subscription ID: {subscription.get('id')}")
                    print(f"⭐️ PUBLIC WEBHOOK: Customer ID: {subscription.get('customer')}")
                    print(f"⭐️ PUBLIC WEBHOOK: Status: {subscription.get('status')}")
                    
                    # Try to extract more detailed information from items
                    if subscription.get('items', {}).get('data'):
                        items = subscription.get('items', {}).get('data', [])
                        for idx, item in enumerate(items):
                            print(f"⭐️ PUBLIC WEBHOOK: Subscription item {idx}:")
                            if isinstance(item, dict):
                                if 'price' in item:
                                    price = item['price']
                                    if isinstance(price, dict) and 'id' in price:
                                        print(f"⭐️ PUBLIC WEBHOOK: Price ID: {price['id']}")
                                    else:
                                        print(f"⭐️ PUBLIC WEBHOOK: Price: {price}")
                            else:
                                print(f"⭐️ PUBLIC WEBHOOK: Item type: {type(item)}")
            except json.JSONDecodeError:
                print("⭐️ PUBLIC WEBHOOK: Could not parse payload as JSON")
                print(f"⭐️ PUBLIC WEBHOOK: Raw payload: {payload}")
        else:
            print("⭐️ PUBLIC WEBHOOK: Empty payload received")
            
        return {"status": "success", "message": "Webhook received and logged"}
    except Exception as e:
        print(f"⭐️ PUBLIC WEBHOOK ERROR: {str(e)}")
        print(f"⭐️ PUBLIC WEBHOOK ERROR type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# Also provide a GET endpoint for testing connectivity
@router.get("/public-webhook")
async def public_stripe_webhook_get_standalone() -> Dict[str, str]:
    print("⭐️ PUBLIC WEBHOOK: Received GET request")
    return {
        "status": "success", 
        "message": "Webhook endpoint is online and accessible",
        "instructions": "Send Stripe webhook events to this URL"
    }
