from fastapi import APIRouter, HTTPException, status, Body
from app.models.schemas import UserMessageInput, ProcessingResultOutput, OperatorResponseInput
from app.core.orchestrator import process_user_message
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger, log_message_processing, log_history_storage

router = APIRouter()

# Existing endpoint for user message processing
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
        # Validate user_text is not empty or whitespace-only
        if not payload.user_text or payload.user_text.strip() == "":
            log_message_processing(payload.phone_number, "FAILED", "User input is empty or contains only whitespace.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User message cannot be empty or contain only whitespace."
            )
        
        log_message_processing(payload.phone_number, "STARTED", "Initiating message processing.")
        result = await process_user_message(payload)
        log_message_processing(payload.phone_number, "COMPLETED", "Message processing completed successfully.")
        return result
    except HTTPException as he:
        log_message_processing(payload.phone_number, "FAILED", f"Error during processing: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number, "FAILED", f"Error during processing: {str(e)}")
        app_logger.error(f"Error processing message for customer {payload.phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )

# New endpoint to submit operator response and update conversation turn
@router.post(
    "/submit_operator_response",
    response_model=dict,
    summary="Submit Operator Response",
    description="Submits the operator's response for a specific user message and updates the conversation history.",
    status_code=status.HTTP_200_OK,
)
async def submit_operator_response(
    payload: OperatorResponseInput = Body(...)
):
    """
    Endpoint to submit the operator's response and update the corresponding conversation turn in the history.
    """
    try:
        log_message_processing(payload.phone_number, "STARTED", "Submitting operator response.")
        success = await vector_db_service.update_conversation_turn(
            phone_number=payload.phone_number,
            timestamp=payload.timestamp,
            user_text=payload.user_text,
            operator_response=payload.operator_response
        )
        if not success:
            log_history_storage(payload.phone_number, False, "Failed to update conversation turn with operator response.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update conversation turn for customer {payload.phone_number}."
            )
        log_history_storage(payload.phone_number, True, "Operator response updated successfully.")
        log_message_processing(payload.phone_number, "COMPLETED", "Operator response submitted successfully.")
        return {"status": "success", "message": "Operator response updated successfully."}
    except HTTPException as he:
        log_message_processing(payload.phone_number, "FAILED", f"Error submitting operator response: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number, "FAILED", f"Error submitting operator response: {str(e)}")
        app_logger.error(f"Error updating operator response for customer {payload.phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )
