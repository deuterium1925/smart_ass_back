from fastapi import APIRouter, HTTPException, status, Body
from app.models.schemas import UserMessageInput, ProcessingResultOutput, OperatorResponseInput
from app.core.orchestrator import process_user_message
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger, log_message_processing, log_history_storage

router = APIRouter()

@router.post(
    "/process",
    response_model=ProcessingResultOutput,
    summary="Process User Message",
    description="Receives a user message, orchestrates agent processing, and returns results/suggestions. Requires an existing customer profile identified by phone_number.",
    status_code=status.HTTP_200_OK,
)
async def handle_process_message(
    payload: UserMessageInput = Body(...)
):
    """
    Endpoint to process a user message for a customer identified by phone_number.
    Orchestrates multiple agents for intent, emotion, and action suggestions.
    Rejects processing if no customer profile exists.
    """
    try:
        # Ensure user_text is not empty or only whitespace
        if not payload.user_text or payload.user_text.strip() == "":
            log_message_processing(payload.phone_number, "FAILED", "User input is empty or contains only whitespace.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User message cannot be empty or contain only whitespace."
            )
        
        log_message_processing(payload.phone_number, "STARTED", "Initiating message processing.")
        result = await process_user_message(payload)
        # Check if the orchestrator returned an error due to missing customer profile
        if "Профиль клиента с номером телефона" in result.consolidated_output:
            log_message_processing(payload.phone_number, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.consolidated_output
            )
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

@router.post(
    "/submit_operator_response",
    response_model=dict,
    summary="Submit Operator Response",
    description="Submits the operator's response for a user message and updates conversation history using turn_id. Requires an existing customer profile.",
    status_code=status.HTTP_200_OK,
)
async def submit_operator_response(
    payload: OperatorResponseInput = Body(...)
):
    """
    Endpoint to update a conversation turn with the operator's response in history.
    Identifies the turn using phone_number and turn_id.
    Rejects operation if no customer profile exists.
    """
    try:
        log_message_processing(payload.phone_number, "STARTED", "Submitting operator response.")
        # Check if customer profile exists before updating history
        customer = await vector_db_service.retrieve_customer(payload.phone_number)
        if not customer:
            log_message_processing(payload.phone_number, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка: Профиль клиента с номером телефона {payload.phone_number} не найден. Пожалуйста, создайте профиль перед обновлением истории."
            )
        success = await vector_db_service.update_conversation_turn(
            phone_number=payload.phone_number,
            turn_id=payload.turn_id,
            operator_response=payload.operator_response
        )
        if not success:
            log_history_storage(payload.phone_number, False, "Failed to update conversation turn with operator response.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update conversation turn for customer {payload.phone_number} with turn_id {payload.turn_id}."
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
