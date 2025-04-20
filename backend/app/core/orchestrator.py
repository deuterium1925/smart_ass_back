import asyncio
import time
from datetime import datetime, timezone  # Added for UTC timestamp
from typing import List
from app.models.schemas import UserMessageInput, ProcessingResultOutput, AgentResponse, Suggestion, HistoryEntry
from app.agents import (
    intent_agent, emotion_agent, knowledge_agent,
    action_agent, summary_agent, qa_agent
)
from app.utils.logger import app_logger, log_history_storage, log_history_retrieval
from app.services.vector_db import vector_db_service
from app.core.config import get_settings

async def process_user_message(payload: UserMessageInput) -> ProcessingResultOutput:
    """
    Orchestrates the processing of a user message through specialized agents for intent, emotion, and knowledge.
    Retrieves customer data and conversation history for personalization and context.
    Stores user messages in long-term memory and handles agent failures gracefully for partial results.
    Enforces a global timeout to prevent hanging in real-time contact center operations.
    """
    user_text = payload.user_text
    phone_number = payload.phone_number
    app_logger.info(f"Orchestrator: Processing message for customer {phone_number}")
    
    # Use the configured REQUEST_TIMEOUT from settings for consistency
    settings = get_settings()
    timeout_seconds = settings.REQUEST_TIMEOUT

    try:
        async with asyncio.timeout(timeout_seconds):
            # Fetch customer profile for personalized agent responses
            customer_data = None
            customer_fetch_error = None
            if phone_number:
                app_logger.debug(f"Fetching customer data for {phone_number}")
                customer_data = await vector_db_service.retrieve_customer(phone_number)
                if not customer_data:
                    app_logger.warning(f"No customer data found for {phone_number}")
                    customer_fetch_error = f"Customer profile not found for phone number {phone_number}. Please create a profile for personalized suggestions."
            else:
                app_logger.error("No phone number provided, processing cannot continue")
                return ProcessingResultOutput(
                    phone_number=phone_number,
                    consolidated_output="Ошибка: не предоставлен номер телефона для обработки запроса",
                    customer_data=None
                )

            # Retrieve conversation history from long-term memory for context
            history_data = await vector_db_service.retrieve_conversation_history(phone_number, limit=10)
            # Convert raw dictionary data to HistoryEntry objects
            history = [HistoryEntry(**entry) for entry in history_data] if history_data else []
            app_logger.debug(f"Retrieved history for customer {phone_number}: {len(history)} turns")
            log_history_retrieval(phone_number, len(history))
            
            # Execute independent agents sequentially to manage API rate limits
            intent_result = await intent_agent.detect_intent(user_text, history=history)
            app_logger.debug(f"Completed Intent Agent for {phone_number}")
            emotion_result = await emotion_agent.detect_emotion(user_text, history=history)
            app_logger.debug(f"Completed Emotion Agent for {phone_number}")
            knowledge_result = await knowledge_agent.find_knowledge(user_text)
            app_logger.debug(f"Completed Knowledge Agent for {phone_number}")

            app_logger.debug(f"Customer {phone_number} - Intent: {intent_result.result}, Emotion: {emotion_result.result}")

            # Store current user message in long-term memory without operator response initially
            timestamp = datetime.now(timezone.utc).isoformat()  # Use UTC ISO timestamp instead of time.time()
            success = await vector_db_service.store_conversation_turn(phone_number, user_text, "", timestamp)
            if not success:
                log_history_storage(phone_number, False, "Failed to store user message.")
                app_logger.warning(f"Failed to store user message for customer {phone_number}; continuing processing")
            else:
                log_history_storage(phone_number, True, "User message stored successfully.")

            # Compile final response with results from all agents
            consolidated_output = f"Обработано: Намерение='{intent_result.result.get('intent', 'N/A')}', Эмоция='{emotion_result.result.get('emotion', 'N/A')}'"
            if customer_fetch_error:
                consolidated_output += f" | {customer_fetch_error}"

            output = ProcessingResultOutput(
                phone_number=phone_number,
                intent=intent_result,
                emotion=emotion_result,
                knowledge=knowledge_result,
                suggestions=await action_agent.suggest_actions(
                    intent_result, emotion_result, knowledge_result, 
                    customer_data=customer_data, history=history
                ),
                summary=await summary_agent.summarize_turn(user_text, intent_result, emotion_result, knowledge_result),
                qa_feedback=await qa_agent.check_quality(user_text, ""),
                consolidated_output=consolidated_output,
                conversation_history=history,  # Include retrieved history for reference
                history_storage_status=success,  # Indicate success/failure of history storage
                customer_data=customer_data  # Provide customer data for frontend use
            )
            app_logger.info(f"Orchestrator: Completed processing for customer {phone_number}")
            return output

    except asyncio.TimeoutError as e:
        app_logger.error(f"Timeout during agent processing for customer {phone_number} after {timeout_seconds}s")
        return ProcessingResultOutput(
            phone_number=phone_number,
            consolidated_output=f"Ошибка: истекло время ожидания обработки ({timeout_seconds} сек)",
            customer_data=None
        )
    except Exception as e:
        app_logger.error(f"Orchestration failed for customer {phone_number}: {e}")
        return ProcessingResultOutput(
            phone_number=phone_number,
            consolidated_output=f"Ошибка обработки: {str(e)}",
            customer_data=None
        )
