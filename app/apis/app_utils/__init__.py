from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ApifyConnectionCheckResult(BaseModel):
    connected: bool
    message: str

@router.get("/check-apify-connection2", response_model=ApifyConnectionCheckResult)
async def check_apify_connection2():
    """Check if Apify API is connected and working properly"""
    from app.apis.apify_integration import check_apify_connection as check_api
    
    try:
        # Call the Apify integration check endpoint
        result = await check_api()
        return ApifyConnectionCheckResult(
            connected=result.connected,
            message=result.message
        )
    except Exception as e:
        return ApifyConnectionCheckResult(
            connected=False,
            message=f"Error checking Apify connection: {str(e)}"
        )