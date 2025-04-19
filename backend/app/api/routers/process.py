from fastapi import APIRouter, HTTPException, status, Body
from app.models.schemas import UserMessageInput, ProcessingResultOutput
from app.core.orchestrator import process_user_message
from app.utils.logger import app_logger, log_message_processing

router = APIRouter()

@router.post(
    "/process",
    response_model=ProcessingResultOutput,
    summary="Process User Message",
    description="Receives a user message, orchestrates agent processing, and returns results/suggestions. Uses phone_number as the sole identifier for the customer.",
    status_code=status.HTTP_200_OK,
)
async def handle_process_message(
    payload: UserMessageInput = Body(...)
):
    """
    Endpoint to process an incoming user message for a specific customer identified by phone_number.
    """
    try:
        log_message_processing(payload.phone_number, "STARTED", "Initiating message processing.")
        result = await process_user_message(payload)
        log_message_processing(payload.phone_number, "COMPLETED", "Message processing completed successfully.")
        return result
    except Exception as e:
        log_message_processing(payload.phone_number, "FAILED", f"Error during processing: {str(e)}")
        app_logger.error(f"Error processing message for customer {payload.phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )
