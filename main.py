import os
import dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()
DATABUTTON_TOKEN = os.getenv("DATABUTTON_TOKEN")

def create_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://prsocials21.onrender.com", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        logger.info("Root endpoint accessed")
        return {"message": "Welcome to the PRSocials Backend API"}

    @app.get("/api/my-subscription")
    async def get_my_subscription():
        if not DATABUTTON_TOKEN:
            logger.error("DATABUTTON_TOKEN not configured")
            raise HTTPException(status_code=500, detail="DATABUTTON_TOKEN not configured")
        headers = {"Authorization": f"Bearer {DATABUTTON_TOKEN}"}
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                logger.info("Fetching my-subscription from Databutton API")
                response = await client.get(
                    "https://api.databutton.com/routes/api/my-subscription",
                    headers=headers
                )
                logger.info(f"Response status: {response.status_code}, URL: {response.url}")
                if response.history:
                    for r in response.history:
                        logger.info(f"Redirected from {r.url} to {r.headers.get('Location')} with status {r.status_code}")
                if not response.is_success:
                    logger.error(f"Databutton response: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=response.status_code, detail=response.text or "Databutton API error")
                # Log raw response for debugging
                logger.info(f"Raw response content: {response.text}")
                try:
                    data = response.json()
                    logger.info("Successfully fetched and parsed my-subscription")
                    return data
                except ValueError as e:
                    logger.error(f"Failed to parse response as JSON: {response.text}")
                    raise HTTPException(status_code=500, detail=f"Invalid JSON from Databutton: {response.text}")
            except httpx.RequestError as e:
                logger.error(f"Network error fetching my-subscription: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error fetching my-subscription: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

    @app.get("/api/subscription-plans")
    async def get_subscription_plans():
        if not DATABUTTON_TOKEN:
            logger.error("DATABUTTON_TOKEN not configured")
            raise HTTPException(status_code=500, detail="DATABUTTON_TOKEN not configured")
        headers = {"Authorization": f"Bearer {DATABUTTON_TOKEN}"}
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                logger.info("Fetching subscription-plans from Databutton API")
                response = await client.get(
                    "https://api.databutton.com/routes/api/subscription-plans",
                    headers=headers
                )
                logger.info(f"Response status: {response.status_code}, URL: {response.url}")
                if response.history:
                    for r in response.history:
                        logger.info(f"Redirected from {r.url} to {r.headers.get('Location')} with status {r.status_code}")
                if not response.is_success:
                    logger.error(f"Databutton response: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=response.status_code, detail=response.text or "Databutton API error")
                # Log raw response for debugging
                logger.info(f"Raw response content: {response.text}")
                try:
                    data = response.json()
                    logger.info("Successfully fetched and parsed subscription-plans")
                    return data
                except ValueError as e:
                    logger.error(f"Failed to parse response as JSON: {response.text}")
                    raise HTTPException(status_code=500, detail=f"Invalid JSON from Databutton: {response.text}")
            except httpx.RequestError as e:
                logger.error(f"Network error fetching subscription-plans: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error fetching subscription-plans: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

    @app.post("/api/create-checkout-session")
    async def create_checkout_session(data: dict):
        logger.info(f"Creating checkout session with data: {data}")
        try:
            return {"status": "success", "checkoutUrl": "https://checkout.stripe.com/example"}
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Checkout error: {str(e)}")

    @app.post("/api/cancel-subscription")
    async def cancel_subscription():
        logger.info("Canceling subscription")
        try:
            return {"status": "success", "message": "Subscription canceled"}
        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Cancel error: {str(e)}")

    @app.post("/api/create-customer-portal-session")
    async def create_customer_portal_session():
        logger.info("Creating customer portal session")
        try:
            return {"url": "https://billing.stripe.com/example"}
        except Exception as e:
            logger.error(f"Error creating customer portal session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Portal error: {str(e)}")

    @app.post("/api/verify-session")
    async def verify_session(data: dict):
        logger.info(f"Verifying session with data: {data}")
        try:
            return {"status": "success", "message": "Session verified"}
        except Exception as e:
            logger.error(f"Error verifying session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Verify error: {str(e)}")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)