import asyncio
import time
from typing import List
from app.models.schemas import UserMessageInput, ProcessingResultOutput, AgentResponse, Suggestion
from app.agents import (
    intent_agent, emotion_agent, knowledge_agent,
    action_agent, summary_agent, qa_agent
)
from app.utils.logger import app_logger
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

        # Retrieve conversation history from long-term memory
        history = await vector_db_service.retrieve_conversation_history(phone_number, limit=10)
        app_logger.debug(f"Retrieved history for customer {phone_number}: {len(history)} turns")
        
        # Update payload history with retrieved history if not provided
        if not payload.history:
            payload.history = [
                {"role": turn["role"], "content": turn["user_text"] if turn["role"] == "user" else turn["operator_response"]}
                for turn in history
            ]

        # Run independent agents in parallel and handle exceptions individually
        tasks = [
            asyncio.create_task(intent_agent.detect_intent(user_text)),
            asyncio.create_task(emotion_agent.detect_emotion(user_text)),
            asyncio.create_task(knowledge_agent.find_knowledge(user_text))
        ]

        # Wait for all tasks to complete, with exceptions returned as results
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)

        # Process results, providing fallback responses for failed tasks
        intent_result = results[0] if not isinstance(results[0], Exception) else AgentResponse(
            agent_name="IntentAgent",
            result={"intent": "unknown", "confidence": 0.0},
            error="Task failed due to exception"
        )
        emotion_result = results[1] if not isinstance(results[1], Exception) else AgentResponse(
            agent_name="EmotionAgent",
            result={"emotion": "unknown", "confidence": 0.0},
            error="Task failed due to exception"
        )
        knowledge_result = results[2] if not isinstance(results[2], Exception) else AgentResponse(
            agent_name="KnowledgeAgent",
            result={"knowledge": [], "message": "Error processing knowledge query."},
            error="Task failed due to exception"
        )

        # Log individual errors for debugging
        if isinstance(results[0], Exception):
            app_logger.error(f"Intent Agent failed for customer {phone_number}: {str(results[0])}")
        if isinstance(results[1], Exception):
            app_logger.error(f"Emotion Agent failed for customer {phone_number}: {str(results[1])}")
        if isinstance(results[2], Exception):
            app_logger.error(f"Knowledge Agent failed for customer {phone_number}: {str(results[2])}")

        app_logger.debug(f"Customer {phone_number} - Intent: {intent_result.result}, Emotion: {emotion_result.result}")

        # Extract operator response from payload if available, otherwise use a fallback
        operator_response = getattr(payload, 'operator_response', '')
        if not operator_response:
            app_logger.debug(f"Customer {phone_number} - No operator response provided, using empty string as fallback")

        # Run dependent agents (Action Suggestion, Summary, QA) in parallel
        # Pass customer_data to action_agent for personalized suggestions
        dependent_tasks = [
            asyncio.create_task(
                action_agent.suggest_actions(intent_result, emotion_result, knowledge_result, customer_data=customer_data)
            ),
            asyncio.create_task(
                summary_agent.summarize_turn(user_text, intent_result, emotion_result, knowledge_result)
            ),
            asyncio.create_task(
                qa_agent.check_quality(user_text, operator_response)
            )
        ]

        # Wait for dependent tasks to complete, handling exceptions individually
        dependent_results = await asyncio.wait_for(
            asyncio.gather(*dependent_tasks, return_exceptions=True), timeout=timeout
        )

        # Process dependent task results with fallbacks
        suggestions = dependent_results[0] if not isinstance(dependent_results[0], Exception) else []
        summary_result = dependent_results[1] if not isinstance(dependent_results[1], Exception) else AgentResponse(
            agent_name="SummaryAgent",
            result={"summary": "Error generating summary."},
            error="Task failed due to exception"
        )
        qa_feedback = dependent_results[2] if not isinstance(dependent_results[2], Exception) else AgentResponse(
            agent_name="QualityAssuranceAgent",
            result={"feedback": "Error during quality check."},
            error="Task failed due to exception"
        )

        # Log errors for dependent tasks
        if isinstance(dependent_results[0], Exception):
            app_logger.error(f"Action Suggestion Agent failed for customer {phone_number}: {str(dependent_results[0])}")
        if isinstance(dependent_results[1], Exception):
            app_logger.error(f"Summary Agent failed for customer {phone_number}: {str(dependent_results[1])}")
        if isinstance(dependent_results[2], Exception):
            app_logger.error(f"QA Agent failed for customer {phone_number}: {str(dependent_results[2])}")

        # Store the current conversation turn in long-term memory
        timestamp = str(int(time.time()))  # Use current timestamp as a simple ordering mechanism
        success = await vector_db_service.store_conversation_turn(phone_number, user_text, operator_response, timestamp)
        if not success:
            app_logger.warning(f"Failed to store conversation turn for customer {phone_number}; continuing processing")

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
