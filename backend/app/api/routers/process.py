from fastapi import APIRouter, HTTPException, status, Body
from typing import Optional  # Add this import
from app.models.schemas import UserMessageInput, ProcessingResultOutput, OperatorResponseInput, AnalysisRequest, ProcessMessageResponse, AgentResponse
from app.core.orchestrator import analyze_conversation, process_automated_agents
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger, log_message_processing, log_history_storage
from app.core.state import customer_queue, active_conversation, queue_lock

router = APIRouter()

@router.post(
    "/process",
    response_model=ProcessMessageResponse,
    summary="Store User Message",
    description="""
    Receives a user message and stores it in conversation history. QA and Summary Agents are NOT run automatically 
    and will only be triggered after the operator submits a response via `/submit_operator_response`. 
    Returns the `timestamp` for the stored message. Requires an existing customer profile identified by `phone_number` in format `89XXXXXXXXX`.
    Adds customer to FIFO queue if they have unresponded messages.
    
    **Frontend Integration Notes**:
    - Use the returned `timestamp` for reference only; it is not required for subsequent `/analyze` or `/submit_operator_response` calls as the system auto-selects the relevant message.
    - QA and Summary results are not available immediately and will be provided only after the operator submits a response or a manual trigger is initiated via `/trigger_automated_agents`.
    - Display a placeholder or loading state for QA and Summary results until the operator response is submitted or manually triggered.
    - Ensure `phone_number` is in format `89XXXXXXXXX` (11 digits starting with 89) before calling this endpoint to avoid validation errors.
    - Check `status` and `message` fields for operation success or error details to handle validation or profile-not-found scenarios gracefully in the UI.
    """,
    status_code=status.HTTP_200_OK,
)
async def handle_process_message(
    payload: UserMessageInput = Body(...)
):
    """
    Endpoint to store a user message for a customer identified by phone_number.
    Stores the message in history without running QA and Summary Agents.
    Rejects processing if no customer profile exists or phone number is invalid.
    Adds customer to FIFO queue if they have unresponded messages.
    """
    try:
        log_message_processing(payload.phone_number, "STARTED", "Initiating message storage.")
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
        stored_timestamp = await vector_db_service.store_conversation_turn(
            phone_number=payload.phone_number,
            user_text=payload.user_text,
            operator_response="",
            timestamp=timestamp
        )
        if not stored_timestamp:
            log_history_storage(payload.phone_number, False, "Failed to store user message.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store user message for customer {payload.phone_number} at timestamp {timestamp}."
            )
        
        # Add customer to queue if not already in queue or active conversation
        async with queue_lock:
            if payload.phone_number not in customer_queue and payload.phone_number != active_conversation:
                customer_queue.append(payload.phone_number)
                app_logger.info(f"Added customer {payload.phone_number} to queue. Queue length: {len(customer_queue)}")
                # Persist queue state to database
                await vector_db_service.save_queue_state(list(customer_queue), active_conversation)
                app_logger.info(f"Persisted queue state after adding {payload.phone_number}")
        
        log_history_storage(payload.phone_number, True, f"User message stored successfully at timestamp {timestamp}.")
        log_message_processing(payload.phone_number, "COMPLETED", "Message storage completed successfully. QA and Summary Agents will run after operator response.")
        return ProcessMessageResponse(
            status="success",
            message="User message stored successfully. QA and Summary Agents will run after operator response.",
            timestamp=timestamp,
            automated_results={
                "summary": AgentResponse(
                    agent_name="SummaryAgent",
                    result={"summary": "Summary will be generated after operator response."},
                    confidence=0.0
                ),
                "qa_feedback": AgentResponse(
                    agent_name="QAAgent",
                    result={"feedback": "QA feedback will be generated after operator response."},
                    confidence=0.0
                )
            }
        )
    except ValueError as ve:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "invalid_input", "FAILED", f"Validation error: {str(ve)}")
        app_logger.error(f"Validation error storing message for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'invalid_input'}: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(ve)}",
        )
    except HTTPException as he:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "unknown", "FAILED", f"Error during storage or processing: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "unknown", "FAILED", f"Error during storage or processing: {str(e)}")
        app_logger.error(f"Error storing message for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'unknown'} at timestamp {timestamp if 'timestamp' in locals() else 'unknown'}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing message for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'unknown'}: {str(e)}",
        )

@router.post(
    "/analyze",
    response_model=ProcessingResultOutput,
    summary="Analyze Conversation On-Demand",
    description="""
    Triggers agent analysis (Intent, Emotion, Knowledge, Action Suggestion, QA) for specific conversation turns or recent history on operator request. 
    Requires an existing customer profile identified by `phone_number` in format `89XXXXXXXXX` and conversation history to exist.
    
    **Frontend Integration Notes**:
    - Use `timestamps` to analyze specific conversation turns (identified by `timestamp` from `/process` responses), or rely on `history_limit` to analyze recent messages.
    - Results include detailed analysis from operator-controlled agents, including QA feedback if an operator response exists in history, which can be used to display suggestions or insights in the UI.
    - `conversation_history` in the response provides the context used for analysis, aiding in displaying relevant chat history.
    - Check `consolidated_output` for a quick summary of analysis results.
    - Analysis will not proceed without conversation history and will return an error in such cases.
    - Ensure `phone_number` is in format `89XXXXXXXXX` (11 digits starting with 89) before calling this endpoint to avoid validation errors.
    """,
    status_code=status.HTTP_200_OK,
)
async def analyze_conversation_request(
    payload: AnalysisRequest = Body(...)
):
    """
    Endpoint to trigger agent analysis for a customer conversation.
    Can analyze specific turn(s) or the most recent history based on limit.
    Rejects processing if no customer profile exists or phone number is invalid.
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
    except ValueError as ve:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "invalid_input", "FAILED", f"Validation error: {str(ve)}")
        app_logger.error(f"Validation error analyzing conversation for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'invalid_input'}: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(ve)}",
        )
    except HTTPException as he:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "unknown", "FAILED", f"Error during analysis: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "unknown", "FAILED", f"Error during analysis: {str(e)}")
        app_logger.error(f"Error analyzing conversation for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'unknown'}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while analyzing conversation for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'unknown'}: {str(e)}",
        )

@router.post(
    "/submit_operator_response",
    response_model=dict,
    summary="Submit Operator Response and Trigger Automated Agents",
    description="""
    Submits the operator's response for the most recent unanswered user message, updates conversation history, 
    and triggers QA and Summary Agents to provide feedback based on the operator's response. 
    Requires an existing customer profile identified by `phone_number` in format `89XXXXXXXXX`.
    If the customer is the active conversation, allows for updating history accordingly.
    
    **Frontend Integration Notes**:
    - The system automatically identifies the most recent unanswered user message to update with the operator's response.
    - Ensure `phone_number` matches the customer profile and is in format `89XXXXXXXXX` (11 digits starting with 89) to avoid orphaned data or validation errors.
    - After submission, QA and Summary results will be available in the response for immediate display. Update any placeholders or loading states with these results.
    """,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/submit_operator_response",
    response_model=dict,
    summary="Submit Operator Response and Trigger Automated Agents",
    description="""
    Submits the operator's response for a user message, updates conversation history, 
    and triggers QA and Summary Agents to provide feedback based on the operator's response. 
    Requires an existing customer profile identified by `phone_number` in format `89XXXXXXXXX`.
    If a specific `timestamp` is provided, updates that conversation turn; otherwise, auto-selects the most recent unanswered turn.
    If no unanswered turns exist, creates a new turn for follow-up communication.
    If the customer is the active conversation, allows for updating history accordingly.
    
    **Frontend Integration Notes**:
    - Optionally provide `timestamp` (from `/process` or `/history`) to target a specific conversation turn. If omitted, the system selects the most recent unanswered message or creates a new turn.
    - If no unanswered messages exist or the targeted turn already has a response, a new turn is created for follow-up communication.
    - Ensure `phone_number` matches the customer profile and is in format `89XXXXXXXXX` (11 digits starting with 89) to avoid orphaned data or validation errors.
    - After submission, QA and Summary results will be available in the response for immediate display. Update any placeholders or loading states with these results.
    """,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/submit_operator_response",
    response_model=dict,
    summary="Submit Operator Response and Trigger Automated Agents",
    description="""
    Submits the operator's response for the most recent unanswered user message, updates conversation history, 
    and triggers Summary Agent to provide feedback based on the operator's response. 
    Requires an existing customer profile identified by `phone_number` in format `89XXXXXXXXX`.
    If a specific `timestamp` is provided, updates that conversation turn; otherwise, auto-selects the most recent unanswered turn.
    If no unanswered turns exist, creates a new turn for follow-up communication.
    If the customer is the active conversation, allows for updating history accordingly.
    
    **Frontend Integration Notes**:
    - Optionally provide `timestamp` (from `/process` or `/history`) to target a specific conversation turn. If omitted, the system selects the most recent unanswered message or creates a new turn.
    - If no unanswered messages exist or the targeted turn already has a response, a new turn is created for follow-up communication.
    - Ensure `phone_number` matches the customer profile and is in format `89XXXXXXXXX` (11 digits starting with 89) to avoid orphaned data or validation errors.
    - After submission, Summary results will be available in the response for immediate display. Update any placeholders or loading states with these results.
    """,
    status_code=status.HTTP_200_OK,
)
async def submit_operator_response(
    payload: OperatorResponseInput = Body(...)
):
    """
    Endpoint to update a conversation turn with the operator's response in history and trigger Summary Agent.
    Uses provided timestamp or auto-identifies the most recent unanswered user message using phone_number.
    Creates a new turn if no unanswered messages exist or if the specified turn already has a response.
    Rejects operation if no customer profile exists or phone number is invalid.
    Checks if the customer is the active conversation.
    """
    try:
        log_message_processing(payload.phone_number, "STARTED", "Submitting operator response and triggering automated agents.")
        async with queue_lock:
            if active_conversation and active_conversation != payload.phone_number:
                app_logger.warning(f"Operator is responding to {payload.phone_number} but active conversation is {active_conversation}.")
                # Optionally enforce active conversation check (disabled for flexibility)
                # raise HTTPException(
                #     status_code=status.HTTP_400_BAD_REQUEST,
                #     detail=f"Cannot respond to {payload.phone_number}. Active conversation is with {active_conversation}. Switch using /next_customer."
                # )

        # Check if customer profile exists before updating history
        customer = await vector_db_service.retrieve_customer(payload.phone_number)
        if not customer:
            log_message_processing(payload.phone_number, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка: Профиль клиента с номером телефона {payload.phone_number} не найден. Пожалуйста, создайте профиль перед обновлением истории."
            )

        timestamp = getattr(payload, 'timestamp', None)  # Safely access timestamp, default to None if not present
        user_text = ""
        history_data = await vector_db_service.retrieve_conversation_history(payload.phone_number, limit=50)
        selected_turn = None

        if timestamp:
            # If timestamp is provided, find the specific turn
            for entry in history_data:
                if entry["timestamp"] == timestamp and entry["role"] == "user":
                    selected_turn = entry
                    break
            if not selected_turn:
                log_message_processing(payload.phone_number, "FAILED", f"Conversation turn not found for timestamp {timestamp}.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation turn not found for timestamp {timestamp} for customer {payload.phone_number}."
                )
            timestamp = selected_turn["timestamp"]
            user_text = selected_turn["user_text"]
            # If the turn already has a response (i.e., a corresponding assistant turn with the same timestamp exists), create a new follow-up turn
            if any(entry["timestamp"] == timestamp and entry["role"] == "assistant" for entry in history_data):
                app_logger.info(f"Turn at timestamp {timestamp} for {payload.phone_number} already has a response. Creating new follow-up turn.")
                from datetime import datetime, timezone
                timestamp = datetime.now(timezone.utc).isoformat()
                user_text = ""  # Empty user_text for follow-up turn initiated by operator
                stored_timestamp = await vector_db_service.store_conversation_turn(
                    phone_number=payload.phone_number,
                    user_text=user_text,
                    operator_response=payload.operator_response,
                    timestamp=timestamp
                )
                if not stored_timestamp:
                    log_history_storage(payload.phone_number, False, "Failed to store follow-up turn.")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to store follow-up turn for customer {payload.phone_number} at timestamp {timestamp}."
                    )
                log_history_storage(payload.phone_number, True, "Follow-up turn stored successfully.")
            else:
                # Update existing turn if no response exists
                success = await vector_db_service.update_conversation_turn(
                    phone_number=payload.phone_number,
                    timestamp=timestamp,
                    operator_response=payload.operator_response
                )
                if not success:
                    log_history_storage(payload.phone_number, False, "Failed to update conversation turn with operator response.")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Failed to update conversation turn for customer {payload.phone_number} at timestamp {timestamp}."
                    )
                log_history_storage(payload.phone_number, True, "Operator response updated successfully.")
        else:
            # If no timestamp provided, auto-select the most recent unanswered turn
            unanswered_turn = await vector_db_service.get_latest_unanswered_turn(payload.phone_number)
            if unanswered_turn:
                timestamp = unanswered_turn["timestamp"]
                user_text = unanswered_turn["user_text"]
                success = await vector_db_service.update_conversation_turn(
                    phone_number=payload.phone_number,
                    timestamp=timestamp,
                    operator_response=payload.operator_response
                )
                if not success:
                    log_history_storage(payload.phone_number, False, "Failed to update conversation turn with operator response.")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Failed to update conversation turn for customer {payload.phone_number} at timestamp {timestamp}."
                    )
                log_history_storage(payload.phone_number, True, "Operator response updated successfully.")
            else:
                # If no unanswered turns, create a new follow-up turn
                app_logger.info(f"No unanswered turns for {payload.phone_number}. Creating new follow-up turn.")
                from datetime import datetime, timezone
                timestamp = datetime.now(timezone.utc).isoformat()
                user_text = ""  # Empty user_text for follow-up turn initiated by operator
                stored_timestamp = await vector_db_service.store_conversation_turn(
                    phone_number=payload.phone_number,
                    user_text=user_text,
                    operator_response=payload.operator_response,
                    timestamp=timestamp
                )
                if not stored_timestamp:
                    log_history_storage(payload.phone_number, False, "Failed to store follow-up turn.")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to store follow-up turn for customer {payload.phone_number} at timestamp {timestamp}."
                    )
                log_history_storage(payload.phone_number, True, "Follow-up turn stored successfully.")

        # Trigger automated agents (Summary) after operator response
        automated_result = await process_automated_agents(
            phone_number=payload.phone_number,
            timestamp=timestamp,
            user_text=user_text,
            operator_response=payload.operator_response
        )

        # Check for remaining unanswered messages and update queue if none exist
        async with queue_lock:
            history_data = await vector_db_service.retrieve_conversation_history(payload.phone_number, limit=50)
            has_unanswered = any(entry["user_text"].strip() and not any(e["timestamp"] == entry["timestamp"] and e["role"] == "assistant" for e in history_data) for entry in history_data if entry["role"] == "user")
            if not has_unanswered and payload.phone_number in customer_queue:
                customer_queue.remove(payload.phone_number)
                app_logger.info(f"Removed customer {payload.phone_number} from queue as no unanswered messages remain. Queue length: {len(customer_queue)}")
                await vector_db_service.save_queue_state(list(customer_queue), active_conversation)
                app_logger.info(f"Persisted queue state after removing {payload.phone_number}")

        log_message_processing(payload.phone_number, "COMPLETED", "Operator response submitted and automated agents processed successfully.")
        return {
            "status": "success",
            "message": "Operator response updated and automated agents processed successfully.",
            "timestamp": timestamp,  # Return the identified or new timestamp for reference
            "automated_results": {
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
        }
    except ValueError as ve:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "invalid_input", "FAILED", f"Validation error: {str(ve)}")
        app_logger.error(f"Validation error updating operator response for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'invalid_input'}: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(ve)}",
        )
    except HTTPException as he:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "unknown", "FAILED", f"Error submitting operator response: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(payload.phone_number if hasattr(payload, 'phone_number') else "unknown", "FAILED", f"Error submitting operator response: {str(e)}")
        app_logger.error(f"Error updating operator response for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'unknown'}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while updating operator response for customer {payload.phone_number if hasattr(payload, 'phone_number') else 'unknown'}: {str(e)}",
        )

@router.post(
    "/trigger_automated_agents/{phone_number}",
    response_model=dict,
    summary="Manually Trigger Automated Agents",
    description="""
    Manually triggers QA and Summary Agents for a specific conversation turn if the operator response 
    has not been submitted within a certain time frame. Requires an existing customer profile identified by `phone_number` in format `89XXXXXXXXX`.
    Optionally accepts a `timestamp` query parameter to target a specific turn; otherwise, selects the most recent turn (prioritizing unanswered messages).
    
    **Frontend Integration Notes**:
    - Use this endpoint to trigger QA and Summary Agents manually if the operator response is delayed indefinitely.
    - Optionally provide `timestamp` as a query parameter to target a specific turn; if omitted, the system selects the most recent conversation turn.
    - Ensure `phone_number` is in format `89XXXXXXXXX` (11 digits starting with 89) before calling this endpoint to avoid validation errors.
    - Display the results once they are returned, updating any placeholders or loading states with QA and Summary feedback.
    """,
    status_code=status.HTTP_200_OK,
)
async def trigger_automated_agents(phone_number: str, timestamp: Optional[str] = None):
    """
    Endpoint to manually trigger QA and Summary Agents for a specific conversation turn or the most recent one.
    Useful for handling cases where operator response is delayed indefinitely.
    Rejects operation if no customer profile exists or if the conversation turn is not found or phone number is invalid.
    """
    try:
        # Normalize and validate phone number
        cleaned_phone = ''.join(filter(str.isdigit, phone_number))
        if len(cleaned_phone) != 11 or not cleaned_phone.startswith('89'):
            log_message_processing(phone_number, "FAILED", "Invalid phone number format.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX)."
            )

        log_message_processing(cleaned_phone, "STARTED", f"Manually triggering automated agents for {'timestamp ' + timestamp if timestamp else 'the most recent turn'}.")
        # Check if customer profile exists
        customer = await vector_db_service.retrieve_customer(cleaned_phone)
        if not customer:
            log_message_processing(cleaned_phone, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка: Профиль клиента с номером телефона {cleaned_phone} не найден."
            )

        # Retrieve history to find the specific turn or most recent
        history_data = await vector_db_service.retrieve_conversation_history(cleaned_phone, limit=50)
        if not history_data:
            log_message_processing(cleaned_phone, "FAILED", "No conversation history found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conversation history found for customer {cleaned_phone}."
            )

        # Select turn based on provided timestamp or auto-select
        selected_turn = None
        if timestamp:
            for entry in history_data:
                if entry["timestamp"] == timestamp:
                    selected_turn = entry
                    break
            if not selected_turn:
                log_message_processing(cleaned_phone, "FAILED", f"Conversation turn not found for timestamp {timestamp}.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation turn not found for timestamp {timestamp} for customer {cleaned_phone}. Suggestion: Fetch recent conversation history via /analyze to get the correct timestamp."
                )
        else:
            # Select the most recent unanswered turn or the latest turn if all are answered
            for entry in reversed(history_data):  # Most recent first
                if entry["user_text"].strip() and not entry["operator_response"].strip():
                    selected_turn = entry
                    break
            if not selected_turn:
                selected_turn = history_data[-1]  # Fallback to the most recent turn if all answered

        timestamp = selected_turn["timestamp"]
        user_text = selected_turn["user_text"]
        operator_response = selected_turn["operator_response"]

        # Trigger automated agents (QA and Summary)
        automated_result = await process_automated_agents(
            phone_number=cleaned_phone,
            timestamp=timestamp,
            user_text=user_text,
            operator_response=operator_response
        )
        log_message_processing(cleaned_phone, "COMPLETED", f"Automated agents triggered manually for timestamp {timestamp}.")
        return {
            "status": "success",
            "message": f"Automated agents triggered successfully for timestamp {timestamp}.",
            "timestamp": timestamp,
            "automated_results": {
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
        }
    except HTTPException as he:
        log_message_processing(phone_number, "FAILED", f"Error triggering automated agents: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(phone_number, "FAILED", f"Error triggering automated agents: {str(e)}")
        app_logger.error(f"Error triggering automated agents for customer {phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while triggering automated agents for customer {phone_number}: {str(e)}",
        )

@router.get(
    "/next_customer",
    response_model=dict,
    summary="Fetch Next Customer from Queue",
    description="""
    Retrieves the next customer from the FIFO queue of customers with unresponded messages and sets them as the active conversation.
    If no customers are in the queue, returns a message indicating the queue is empty.
    Ensures only one customer is active at a time for the operator.
    
    **Frontend Integration Notes**:
    - Use this endpoint when the operator finishes with the current customer to move to the next one in the queue.
    - The returned `phone_number` becomes the active conversation for the operator to handle.
    - If the queue is empty, display a message to the operator indicating no pending customers.
    """,
    status_code=status.HTTP_200_OK,
)
async def get_next_customer():
    """
    Endpoint to fetch the next customer from the FIFO queue and set them as the active conversation.
    Updates the active_conversation state and removes the customer from the queue.
    Returns the phone number of the next customer or a message if the queue is empty.
    Persists the updated queue state to the database.
    """
    try:
        async with queue_lock:
            global active_conversation
            if len(customer_queue) == 0:
                app_logger.info("Queue is empty. No customers to process.")
                return {
                    "status": "empty",
                    "message": "No customers in queue to process.",
                    "phone_number": None
                }
            next_customer = customer_queue.popleft()
            active_conversation = next_customer
            app_logger.info(f"Assigned next customer {next_customer} as active conversation. Queue length: {len(customer_queue)}")
            # Persist updated queue state to database
            await vector_db_service.save_queue_state(list(customer_queue), active_conversation)
            app_logger.info(f"Persisted queue state after assigning {next_customer} as active conversation")
            return {
                "status": "success",
                "message": f"Customer {next_customer} is now the active conversation.",
                "phone_number": next_customer
            }
    except Exception as e:
        app_logger.error(f"Error fetching next customer from queue: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching the next customer: {str(e)}",
        )

@router.get(
    "/queue_status",
    response_model=dict,
    summary="Get Queue Status",
    description="""
    Retrieves the current status of the customer queue, including the number of waiting customers and optionally a masked list of their phone numbers.
    Provides feedback to the operator about the workload.
    
    **Frontend Integration Notes**:
    - Use this endpoint to display the number of pending customers in the queue to the operator.
    - The `queue_length` indicates how many customers are waiting for a response.
    - The `waiting_customers` list provides partially masked phone numbers for privacy (e.g., 89****XX**).
    - If an active conversation exists, it is included for reference.
    """,
    status_code=status.HTTP_200_OK,
)
async def get_queue_status():
    """
    Endpoint to fetch the current queue status, including queue length and a list of waiting customers with masked phone numbers.
    Returns the active conversation if one exists.
    """
    try:
        async with queue_lock:
            queue_length = len(customer_queue)
            # Mask phone numbers for privacy (show first 2 and last 2 digits, mask middle)
            masked_customers = [
                f"{phone[:2]}****{phone[-2:]}" for phone in customer_queue
            ] if customer_queue else []
            app_logger.info(f"Queue status requested: {queue_length} customers in queue, active conversation: {active_conversation if active_conversation else 'None'}")
            response = {
                "status": "success",
                "queue_length": queue_length,
                "waiting_customers": masked_customers,
                "active_conversation": f"{active_conversation[:2]}****{active_conversation[-2:]}" if active_conversation else None
            }
            return response
    except Exception as e:
        app_logger.error(f"Error fetching queue status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching queue status: {str(e)}",
        )

@router.get(
    "/cleanup_queue",
    response_model=dict,
    summary="Cleanup Queue of Customers with No Unanswered Messages",
    description="""
    Removes customers from the queue who have no unanswered messages. This ensures the queue reflects only customers needing operator attention.
    
    **Frontend Integration Notes**:
    - Use this endpoint to ensure the queue is up-to-date, especially after operator responses or manual cleanups.
    - Display the results (number of removed customers and new queue length) to provide feedback to the operator.
    """,
    status_code=status.HTTP_200_OK,
)
async def cleanup_queue():
    """
    Endpoint to remove customers from the queue who have no unanswered messages.
    Returns the number of removed customers and updated queue length.
    Persists the updated queue state to the database.
    """
    try:
        async with queue_lock:
            initial_length = len(customer_queue)
            customers_to_remove = []
            for phone_number in customer_queue:
                history = await vector_db_service.retrieve_conversation_history(phone_number, limit=50)
                has_unanswered = any(entry["user_text"].strip() and not entry["operator_response"].strip() for entry in history)
                if not has_unanswered:
                    customers_to_remove.append(phone_number)
            for phone_number in customers_to_remove:
                customer_queue.remove(phone_number)
                app_logger.info(f"Removed customer {phone_number} from queue during cleanup (no unanswered messages).")
            await vector_db_service.save_queue_state(list(customer_queue), active_conversation)
            app_logger.info(f"Queue cleanup completed. Removed {len(customers_to_remove)} customers. New queue length: {len(customer_queue)}")
            return {
                "status": "success",
                "message": f"Queue cleanup completed. Removed {len(customers_to_remove)} customers. New queue length: {len(customer_queue)}.",
                "removed_customers": len(customers_to_remove),
                "initial_queue_length": initial_length,
                "current_queue_length": len(customer_queue)
            }
    except Exception as e:
        app_logger.error(f"Error during queue cleanup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during queue cleanup: {str(e)}",
        )

@router.get(
    "/history/{phone_number}",
    response_model=dict,
    summary="Retrieve Conversation History",
    description="""
    Retrieves the conversation history for a specific customer identified by `phone_number` in format `89XXXXXXXXX`.
    Returns a list of conversation turns including user messages and operator responses, ordered by timestamp.
    
    **Frontend Integration Notes**:
    - Use this endpoint to fetch the complete message history for a customer without triggering analysis.
    - Ensure `phone_number` is in format `89XXXXXXXXX` (11 digits starting with 89) to avoid validation errors.
    - The response includes a list of history entries with user text, operator responses, and timestamps.
    - Use the `limit` query parameter to control the number of recent history entries retrieved (default is 50).
    """,
    status_code=status.HTTP_200_OK,
)
async def retrieve_history(phone_number: str, limit: int = 50):
    """
    Endpoint to fetch the conversation history for a customer identified by phone_number.
    Returns a list of history entries ordered by timestamp.
    Rejects operation if no customer profile exists or phone number is invalid.
    """
    try:
        # Normalize and validate phone number
        cleaned_phone = ''.join(filter(str.isdigit, phone_number))
        if len(cleaned_phone) != 11 or not cleaned_phone.startswith('89'):
            log_message_processing(phone_number, "FAILED", "Invalid phone number format.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX)."
            )

        log_message_processing(cleaned_phone, "STARTED", f"Retrieving conversation history with limit {limit}.")
        # Check if customer profile exists
        customer = await vector_db_service.retrieve_customer(cleaned_phone)
        if not customer:
            log_message_processing(cleaned_phone, "FAILED", "Customer profile not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка: Профиль клиента с номером телефона {cleaned_phone} не найден."
            )

        # Retrieve conversation history
        history_data = await vector_db_service.retrieve_conversation_history(cleaned_phone, limit=limit)
        if not history_data:
            log_message_processing(cleaned_phone, "COMPLETED", "No conversation history found.")
            return {
                "status": "success",
                "message": f"No conversation history found for customer {cleaned_phone}.",
                "history": []
            }

        log_message_processing(cleaned_phone, "COMPLETED", f"Retrieved {len(history_data)} conversation turns.")
        return {
            "status": "success",
            "message": f"Retrieved conversation history for customer {cleaned_phone}.",
            "history": history_data
        }
    except HTTPException as he:
        log_message_processing(phone_number, "FAILED", f"Error retrieving history: {str(he.detail)}")
        raise
    except Exception as e:
        log_message_processing(phone_number, "FAILED", f"Error retrieving history: {str(e)}")
        app_logger.error(f"Error retrieving conversation history for customer {phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving history for customer {phone_number}: {str(e)}",
        )
