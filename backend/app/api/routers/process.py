from fastapi import APIRouter, HTTPException, status, Body
from app.models.schemas import UserMessageInput, ProcessingResultOutput
from app.core.orchestrator import process_user_message
from app.utils.logger import app_logger

router = APIRouter()

@router.post(
    "/process",
    response_model=ProcessingResultOutput,
    summary="Process User Message",
    description="Receives a user message, orchestrates agent processing, and returns results/suggestions.",
    status_code=status.HTTP_200_OK,
)
async def handle_process_message(
    payload: UserMessageInput = Body(...)
):
    """
    Endpoint to process an incoming user message within a specific session.
    """
    try:
        result = await process_user_message(payload)
        return result
    except Exception as e:
        app_logger.error(f"Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )