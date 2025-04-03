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

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://prsocials21.onrender.com", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
        allow_headers=["*"],  # Allow all headers
    )

    @app.get("/")
    async def root():
        logger.info("Root endpoint accessed")
        return {"message": "Welcome to the PRSocials Backend API"}

    @app.get("/api/proxy/my-subscription")
    async def proxy_my_subscription():
        if not DATABUTTON_TOKEN:
            logger.error("DATABUTTON_TOKEN not configured")
            raise HTTPException(status_code=500, detail="DATABUTTON_TOKEN not configured")
        headers = {"Authorization": f"Bearer {DATABUTTON_TOKEN}"}
        async with httpx.AsyncClient() as client:
            try:
                logger.info("Fetching my-subscription from Databutton API")
                response = await client.get(
                    "https://api.databutton.com/routes/api/my-subscription",
                    headers=headers
                )
                response.raise_for_status()
                logger.info("Successfully fetched my-subscription")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error from Databutton: {e.response.status_code} - {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except Exception as e:
                logger.error(f"Unexpected error fetching my-subscription: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

    @app.get("/api/proxy/subscription-plans")
    async def proxy_subscription_plans():
        if not DATABUTTON_TOKEN:
            logger.error("DATABUTTON_TOKEN not configured")
            raise HTTPException(status_code=500, detail="DATABUTTON_TOKEN not configured")
        headers = {"Authorization": f"Bearer {DATABUTTON_TOKEN}"}
        async with httpx.AsyncClient() as client:
            try:
                logger.info("Fetching subscription-plans from Databutton API")
                response = await client.get(
                    "https://api.databutton.com/routes/api/subscription-plans",
                    headers=headers
                )
                response.raise_for_status()
                logger.info("Successfully fetched subscription-plans")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error from Databutton: {e.response.status_code} - {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except Exception as e:
                logger.error(f"Unexpected error fetching subscription-plans: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)