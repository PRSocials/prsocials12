import os
import pathlib
import json
import dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Load environment variables
dotenv.load_dotenv()

# Load additional environment variables for Stripe, OpenAI, Apify, and Databutton
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
DATABUTTON_PROJECT_ID = os.getenv("DATABUTTON_PROJECT_ID")
DATABUTTON_TOKEN = os.getenv("DATABUTTON_TOKEN")

from databutton_app.mw.auth_mw import AuthConfig, get_authorized_user

def get_router_config() -> dict:
    try:
        # Note: This file is not available to the agent
        cfg = json.loads(open("routers.json").read())
    except:
        return False
    return cfg

def is_auth_disabled(router_config: dict, name: str) -> bool:
    return router_config["routers"][name]["disableAuth"]

def import_api_routers() -> APIRouter:
    """Create top level router including all user defined endpoints."""
    routes = APIRouter(prefix="/routes")

    router_config = get_router_config()

    src_path = pathlib.Path(__file__).parent

    # Import API routers from "src/app/apis/*/__init__.py"
    apis_path = src_path / "app" / "apis"

    api_names = [
        p.relative_to(apis_path).parent.as_posix()
        for p in apis_path.glob("*/__init__.py")
    ]

    api_module_prefix = "app.apis."

    for name in api_names:
        print(f"Importing API: {name}")
        try:
            api_module = __import__(api_module_prefix + name, fromlist=[name])
            api_router = getattr(api_module, "router", None)
            if isinstance(api_router, APIRouter):
                routes.include_router(
                    api_router,
                    dependencies=(
                        []
                        if is_auth_disabled(router_config, name)
                        else [Depends(get_authorized_user)]
                    ),
                )
        except Exception as e:
            print(e)
            continue

    print(routes.routes)

    return routes

def get_firebase_config() -> dict | None:
    extensions = os.environ.get("DATABUTTON_EXTENSIONS", "[]")
    extensions = json.loads(extensions)

    for ext in extensions:
        if ext["name"] == "firebase-auth":
            return ext["config"]["firebaseConfig"]

    return None

def create_app() -> FastAPI:
    """Create the app. This is called by uvicorn with the factory option to construct the app object."""
    app = FastAPI()

    # Add CORS middleware to allow frontend requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://prsocials21.onrender.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Define root endpoint
    @app.get("/")
    async def root():
        return {"message": "Welcome to the PRSocials Backend API"}

    # Proxy endpoint for Databutton subscription
    @app.get("/api/proxy/my-subscription")
    async def proxy_my_subscription():
        if not DATABUTTON_TOKEN:
            raise HTTPException(status_code=500, detail="DATABUTTON_TOKEN not configured")
        headers = {"Authorization": f"Bearer {DATABUTTON_TOKEN}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.databutton.com/routes/api/my-subscription",
                    headers=headers
                )
                response.raise_for_status()  # Raise an exception for bad status codes
                return response.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

    # Proxy endpoint for Databutton subscription plans
    @app.get("/api/proxy/subscription-plans")
    async def proxy_subscription_plans():
        if not DATABUTTON_TOKEN:
            raise HTTPException(status_code=500, detail="DATABUTTON_TOKEN not configured")
        headers = {"Authorization": f"Bearer {DATABUTTON_TOKEN}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.databutton.com/routes/api/subscription-plans",
                    headers=headers
                )
                response.raise_for_status()  # Raise an exception for bad status codes
                return response.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

    # Include API routers
    app.include_router(import_api_routers())

    # Log all routes for debugging
    for route in app.routes:
        if hasattr(route, "methods"):
            for method in route.methods:
                print(f"{method} {route.path}")

    # Set up Firebase auth config
    firebase_config = get_firebase_config()

    if firebase_config is None:
        print("No firebase config found")
        app.state.auth_config = None
    else:
        print("Firebase config found")
        auth_config = {
            "jwks_url": "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com",
            "audience": firebase_config["projectId"],
            "header": "authorization",
        }
        app.state.auth_config = AuthConfig(**auth_config)

    return app

# Create the app instance
app = create_app()

# Ensure the app binds to the correct host and port for Render
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Render provides PORT env var
    uvicorn.run(app, host="0.0.0.0", port=port)