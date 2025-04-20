from fastapi import APIRouter, HTTPException, status, Body
from app.models.schemas import UserMessageInput, ProcessingResultOutput, OperatorResponseInput, AnalysisRequest, ProcessMessageResponse, AgentResponse
from app.core.orchestrator import analyze_conversation, process_automated_agents
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger, log_message_processing, log_history_storage

router = APIRouter()

@router.post(
    "/process",
    response_model=ProcessMessageResponse,
    summary="Store User Message and Run Automated Agents",
    description="""
    Receives a user message, stores it in conversation history, and automatically runs QA and Summary Agents in the background. 
    Returns the `turn_id` for the stored message and results from automated agents for immediate reference. 
    Requires an existing customer profile identified by `phone_number`.
    
    **Frontend Integration Notes**:
    - Use the returned `turn_id` to reference this message in subsequent `/analyze` or `/submit_operator_response` calls.
    - Automated results include `summary` and `qa_feedback`, which can be displayed immediately to operators for quick insights.
    - Check `status` and `message` fields for operation success or error details.
    """,
    status_code=status.HTTP_200_OK,
)
async def handle_process_message(
    payload: UserMessageInput = Body(...)
):
    """
    Endpoint to store a user message for a customer identified by phone_number.
    Stores the message in history and automatically runs QA and Summary Agents.
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
        
        log_message_processing(payload.phone_number, "STARTED", "Initiating message storage and automated processing.")
        # Check if customer profile exists
        customer = await vector_db_service.retrieve_customer(payload.phone_number)
        if not customer:
            log_message_processing(payload.phone_number, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка: Профиль клиента с номером телефона {payload.phone_number} не найден. Пожалуйста, создайте профиль перед обработкой сообщений."
            )
        
        # Store the message in history without operator response
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        turn_id = await vector_db_service.store_conversation_turn(
            phone_number=payload.phone_number,
            user_text=payload.user_text,
            operator_response="",
            timestamp=timestamp
        )
        if not turn_id:
            log_history_storage(payload.phone_number, False, "Failed to store user message.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store user message for customer {payload.phone_number}."
            )
        
        log_history_storage(payload.phone_number, True, f"User message stored successfully with turn_id {turn_id}.")
        
        # Run automated agents (QA and Summary) in the background
        automated_result = await process_automated_agents(payload.phone_number, turn_id, payload.user_text)
        log_message_processing(payload.phone_number, "COMPLETED", "Message storage and automated processing completed successfully.")
        return ProcessMessageResponse(
            status="success",
            message="User message stored and automated agents processed successfully.",
            turn_id=turn_id,
            automated_results={
                "summary": automated_result.get("summary", AgentResponse(
                    agent_name="SummaryAgent",
                    result={"summary": "Failed to generate summary."},
                    confidence=0.0
                )),
                "qa_feedback": automated_result.get("qa_feedback", AgentResponse(
                    agent_name="QAAgent",
                    result={"feedback": "Failed to generate QA feedback."},
                    confidence=0.0
                ))
            }
        )
    except HTTPException as he:
        log_message_processing(payload.phone_number, "FAILED", f"Error during storage or processing: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number, "FAILED", f"Error during storage or processing: {str(e)}")
        app_logger.error(f"Error storing message or processing automated agents for customer {payload.phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@router.post(
    "/analyze",
    response_model=ProcessingResultOutput,
    summary="Analyze Conversation On-Demand",
    description="""
    Triggers agent analysis (Intent, Emotion, Knowledge, Action Suggestion) for specific conversation turns or recent history on operator request. 
    Requires an existing customer profile identified by `phone_number`.
    
    **Frontend Integration Notes**:
    - Use `turn_ids` to analyze specific conversation turns (identified by `turn_id` from `/process` responses), or rely on `history_limit` to analyze recent messages.
    - Results include detailed analysis from operator-controlled agents, which can be used to display suggestions or insights in the UI.
    - `conversation_history` in the response provides the context used for analysis, aiding in displaying relevant chat history.
    - Check `consolidated_output` for a quick summary of analysis results.
    """,
    status_code=status.HTTP_200_OK,
)
async def analyze_conversation_request(
    payload: AnalysisRequest = Body(...)
):
    """
    Endpoint to trigger agent analysis for a customer conversation.
    Can analyze specific turn(s) or the most recent history based on limit.
    Rejects processing if no customer profile exists.
    """
    try:
        log_message_processing(payload.phone_number, "STARTED", "Initiating conversation analysis.")
        # Check if customer profile exists
        customer = await vector_db_service.retrieve_customer(payload.phone_number)
        if not customer:
            log_message_processing(payload.phone_number, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка: Профиль клиента с номером телефона {payload.phone_number} не найден. Пожалуйста, создайте профиль перед анализом."
            )
        
        result = await analyze_conversation(payload)
        log_message_processing(payload.phone_number, "COMPLETED", "Conversation analysis completed successfully.")
        return result
    except HTTPException as he:
        log_message_processing(payload.phone_number, "FAILED", f"Error during analysis: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number, "FAILED", f"Error during analysis: {str(e)}")
        app_logger.error(f"Error analyzing conversation for customer {payload.phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@router.post(
    "/submit_operator_response",
    response_model=dict,
    summary="Submit Operator Response",
    description="""
    Submits the operator's response for a user message and updates conversation history using `turn_id`. 
    Requires an existing customer profile identified by `phone_number`.
    
    **Frontend Integration Notes**:
    - Use the `turn_id` returned by `/process` to update the corresponding conversation turn with the operator's response.
    - Ensure `phone_number` matches the customer profile to avoid orphaned data.
    """,
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
