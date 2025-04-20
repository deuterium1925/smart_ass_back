import asyncio
import time
from typing import List
from app.models.schemas import UserMessageInput, ProcessingResultOutput, AgentResponse, Suggestion
from app.agents import (
    intent_agent, emotion_agent, knowledge_agent,
    action_agent, summary_agent, qa_agent
)
from app.utils.logger import app_logger, log_history_storage, log_history_retrieval
from app.services.vector_db import vector_db_service

async def process_user_message(payload: UserMessageInput) -> ProcessingResultOutput:
    """
    Orchestrates the processing of a user message through multiple specialized agents.
    Fetches customer data before processing for personalized responses.
    Handles individual agent failures gracefully to ensure partial results are returned.
    Incorporates long-term memory by retrieving and updating conversation history using phone_number.
    """
    user_text = payload.user_text
    phone_number = payload.phone_number
    app_logger.info(f"Orchestrator: Processing message for customer {phone_number}")
    timeout = 30.0

    try:
        # Fetch customer data if phone_number is provided
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

        # Retrieve conversation history from long-term memory (server-side only)
        history = await vector_db_service.retrieve_conversation_history(phone_number, limit=10)
        app_logger.debug(f"Retrieved history for customer {phone_number}: {len(history)} turns")
        log_history_retrieval(phone_number, len(history))
        
        # Format history for agent processing (server-side history only)
        formatted_history = [
            {"role": turn["role"], "content": turn["user_text"] if turn["role"] == "user" else turn["operator_response"]}
            for turn in history
        ]

        # Run independent agents sequentially to avoid rate limits
        intent_result = await intent_agent.detect_intent(user_text)
        app_logger.debug(f"Completed Intent Agent for {phone_number}")
        emotion_result = await emotion_agent.detect_emotion(user_text)
        app_logger.debug(f"Completed Emotion Agent for {phone_number}")
        knowledge_result = await knowledge_agent.find_knowledge(user_text)
        app_logger.debug(f"Completed Knowledge Agent for {phone_number}")

        app_logger.debug(f"Customer {phone_number} - Intent: {intent_result.result}, Emotion: {emotion_result.result}")

        # Extract operator response from payload if available, otherwise use a fallback
        operator_response = getattr(payload, 'operator_response', '')
        if not operator_response:
            app_logger.debug(f"Customer {phone_number} - No operator response provided, using empty string as fallback")

        # Run dependent agents sequentially to avoid rate limits
        suggestions = await action_agent.suggest_actions(intent_result, emotion_result, knowledge_result, customer_data=customer_data)
        app_logger.debug(f"Completed Action Agent for {phone_number}")
        summary_result = await summary_agent.summarize_turn(user_text, intent_result, emotion_result, knowledge_result)
        app_logger.debug(f"Completed Summary Agent for {phone_number}")
        qa_feedback = await qa_agent.check_quality(user_text, operator_response)
        app_logger.debug(f"Completed QA Agent for {phone_number}")

        # Store the current conversation turn in long-term memory
        timestamp = str(int(time.time()))  # Use current timestamp as a simple ordering mechanism
        success = await vector_db_service.store_conversation_turn(phone_number, user_text, operator_response, timestamp)
        if not success:
            log_history_storage(phone_number, False, "Failed to store conversation turn.")
            app_logger.warning(f"Failed to store conversation turn for customer {phone_number}; continuing processing")
        else:
            log_history_storage(phone_number, True, "Conversation turn stored successfully.")

        # Assemble final response
        consolidated_output = f"Обработано: Намерение='{intent_result.result.get('intent', 'N/A')}', Эмоция='{emotion_result.result.get('emotion', 'N/A')}'"
        if customer_fetch_error:
            consolidated_output += f" | {customer_fetch_error}"

        output = ProcessingResultOutput(
            phone_number=phone_number,
            intent=intent_result,
            emotion=emotion_result,
            knowledge=knowledge_result,
            suggestions=suggestions,
            summary=summary_result,
            qa_feedback=qa_feedback,
            consolidated_output=consolidated_output,
            conversation_history=history,  # Include retrieved history
            history_storage_status=success,  # Indicate storage status
            customer_data=customer_data  # Include customer data for frontend
        )
        app_logger.info(f"Orchestrator: Completed processing for customer {phone_number}")
        return output

    except asyncio.TimeoutError as e:
        app_logger.error(f"Timeout during agent processing for customer {phone_number}")
        return ProcessingResultOutput(
            phone_number=phone_number,
            consolidated_output="Ошибка: истекло время ожидания обработки",
            customer_data=None
        )
    except Exception as e:
        app_logger.error(f"Orchestration failed for customer {phone_number}: {e}")
        return ProcessingResultOutput(
            phone_number=phone_number,
            consolidated_output=f"Ошибка обработки: {str(e)}",
            customer_data=None
        )
