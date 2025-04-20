import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.models.schemas import UserMessageInput, ProcessingResultOutput, AgentResponse, Suggestion, HistoryEntry, AnalysisRequest
from app.agents import (
    intent_agent, emotion_agent, knowledge_agent,
    action_agent, summary_agent, qa_agent
)
from app.utils.logger import app_logger, log_history_storage, log_history_retrieval
from app.services.vector_db import vector_db_service
from app.core.config import get_settings

async def process_automated_agents(phone_number: str, turn_id: str, user_text: str) -> Dict[str, Any]:
    """
    Run automated agents (QA and Summary) after a user message is stored.
    Returns results of automated agents for inclusion in the response.
    """
    app_logger.info(f"Orchestrator: Running automated agents for customer {phone_number}, turn_id {turn_id}")
    settings = get_settings()
    timeout_seconds = settings.REQUEST_TIMEOUT

    try:
        async with asyncio.timeout(timeout_seconds):
            # Retrieve customer data and history for context
            customer_data = await vector_db_service.retrieve_customer(phone_number)
            if not customer_data:
                app_logger.error(f"No customer data found for {phone_number}. Skipping automated agents.")
                return {
                    "summary": {"agent_name": "SummaryAgent", "result": {"summary": "Customer profile not found."}, "confidence": 0.0, "error": "Customer profile not found."},
                    "qa_feedback": {"agent_name": "QAAgent", "result": {"feedback": "Customer profile not found."}, "confidence": 0.0, "error": "Customer profile not found."}
                }

            history_data = await vector_db_service.retrieve_conversation_history(phone_number, limit=10)
            history = [HistoryEntry(**entry) for entry in history_data] if history_data else []
            app_logger.debug(f"Retrieved history for automated agents for customer {phone_number}: {len(history)} turns")
            log_history_retrieval(phone_number, len(history))

            # Run automated agents concurrently
            summary_task = asyncio.create_task(summary_agent.summarize_conversation(history, user_text))
            qa_task = asyncio.create_task(qa_agent.check_quality(user_text, ""))

            summary_result, qa_result = await asyncio.gather(summary_task, qa_task, return_exceptions=True)

            if isinstance(summary_result, Exception):
                app_logger.error(f"Summary Agent failed for {phone_number}: {str(summary_result)}")
                summary_result = AgentResponse(
                    agent_name="SummaryAgent",
                    result={"summary": "Failed to generate summary."},
                    confidence=0.0,
                    error=f"Agent failed: {str(summary_result)}"
                )
            if isinstance(qa_result, Exception):
                app_logger.error(f"QA Agent failed for {phone_number}: {str(qa_result)}")
                qa_result = AgentResponse(
                    agent_name="QAAgent",
                    result={"feedback": "Failed to generate QA feedback."},
                    confidence=0.0,
                    error=f"Agent failed: {str(qa_result)}"
                )

            app_logger.info(f"Orchestrator: Completed automated agents for customer {phone_number}")
            return {
                "summary": summary_result,
                "qa_feedback": qa_result
            }

    except asyncio.TimeoutError as e:
        app_logger.error(f"Timeout during automated agent processing for customer {phone_number} after {timeout_seconds}s")
        return {
            "summary": {"agent_name": "SummaryAgent", "result": {"summary": "Timeout error."}, "confidence": 0.0, "error": f"Timeout after {timeout_seconds}s"},
            "qa_feedback": {"agent_name": "QAAgent", "result": {"feedback": "Timeout error."}, "confidence": 0.0, "error": f"Timeout after {timeout_seconds}s"}
        }
    except Exception as e:
        app_logger.error(f"Automated agent processing failed for customer {phone_number}: {e}")
        return {
            "summary": {"agent_name": "SummaryAgent", "result": {"summary": "Processing error."}, "confidence": 0.0, "error": str(e)},
            "qa_feedback": {"agent_name": "QAAgent", "result": {"feedback": "Processing error."}, "confidence": 0.0, "error": str(e)}
        }

async def analyze_conversation(payload: AnalysisRequest) -> ProcessingResultOutput:
    """
    Analyze conversation history for a customer based on specific turn IDs or recent history.
    Orchestrates agent processing for intent, emotion, knowledge, and suggestions.
    Ensures dependencies are handled by running prerequisite agents (Intent, Emotion) before dependent agents (Action).
    """
    phone_number = payload.phone_number
    turn_ids = payload.turn_ids
    history_limit = payload.history_limit
    app_logger.info(f"Orchestrator: Analyzing conversation for customer {phone_number}")
    
    settings = get_settings()
    timeout_seconds = settings.REQUEST_TIMEOUT

    try:
        async with asyncio.timeout(timeout_seconds):
            customer_data = await vector_db_service.retrieve_customer(phone_number)
            if not customer_data:
                app_logger.error(f"No customer data found for {phone_number}. Rejecting analysis.")
                return ProcessingResultOutput(
                    phone_number=phone_number,
                    consolidated_output=f"Ошибка: Профиль клиента с номером телефона {phone_number} не найден.",
                    customer_data=None
                )

            # Retrieve conversation history based on turn_ids or limit
            history_data = await vector_db_service.retrieve_conversation_history(phone_number, limit=history_limit)
            history = [HistoryEntry(**entry) for entry in history_data] if history_data else []
            app_logger.debug(f"Retrieved history for customer {phone_number}: {len(history)} turns")
            log_history_retrieval(phone_number, len(history))

            # Filter by specific turn_ids if provided
            if turn_ids:
                history = [entry for entry in history if entry.turn_id in turn_ids]
                if not history:
                    app_logger.warning(f"No history found for specified turn_ids for customer {phone_number}")
                    return ProcessingResultOutput(
                        phone_number=phone_number,
                        consolidated_output=f"Ошибка: Не найдено сообщений для указанных turn_ids.",
                        customer_data=customer_data,
                        conversation_history=[]
                    )
                app_logger.debug(f"Filtered history to {len(history)} turns based on turn_ids for customer {phone_number}")

            # Prepare batch user text for analysis (concatenate multiple messages)
            batch_user_text = ""
            if history:
                user_messages = [entry.user_text for entry in history if entry.user_text.strip()]
                batch_user_text = "\n".join(user_messages) if user_messages else "Анализ проводится на основе истории без нового сообщения."
            else:
                batch_user_text = "Анализ проводится на основе истории без нового сообщения."
            app_logger.debug(f"Batch user text for analysis: {batch_user_text[:100]}...")

            # Execute independent prerequisite agents concurrently for batch processing
            intent_task = asyncio.create_task(intent_agent.detect_intent(batch_user_text, history=history))
            emotion_task = asyncio.create_task(emotion_agent.detect_emotion(batch_user_text, history=history))
            knowledge_task = asyncio.create_task(knowledge_agent.find_knowledge(batch_user_text))
            
            intent_result, emotion_result, knowledge_result = await asyncio.gather(
                intent_task, emotion_task, knowledge_task, return_exceptions=True
            )
            
            # Handle potential exceptions or timeouts per agent
            if isinstance(intent_result, Exception):
                app_logger.error(f"Intent Agent failed for {phone_number}: {str(intent_result)}")
                intent_result = AgentResponse(
                    agent_name="IntentAgent",
                    result={"intent": "unknown", "confidence": 0.0},
                    confidence=0.0,
                    error=f"Agent failed: {str(intent_result)}"
                )
            if isinstance(emotion_result, Exception):
                app_logger.error(f"Emotion Agent failed for {phone_number}: {str(emotion_result)}")
                emotion_result = AgentResponse(
                    agent_name="EmotionAgent",
                    result={"emotion": "neutral", "confidence": 0.0},
                    confidence=0.0,
                    error=f"Agent failed: {str(emotion_result)}"
                )
            if isinstance(knowledge_result, Exception):
                app_logger.error(f"Knowledge Agent failed for {phone_number}: {str(knowledge_result)}")
                knowledge_result = AgentResponse(
                    agent_name="KnowledgeAgent",
                    result={"knowledge": [], "message": "Error processing knowledge query."},
                    confidence=0.0,
                    error=f"Agent failed: {str(knowledge_result)}"
                )
            
            app_logger.debug(f"Completed Independent Agents for analysis of {phone_number}")
            consolidated_output = f"Обработано: Намерение='{intent_result.result.get('intent', 'N/A')}', Эмоция='{emotion_result.result.get('emotion', 'N/A')}'"

            # Run dependent agent (Action Suggestion) using results from prerequisites
            suggestions_task = asyncio.create_task(action_agent.suggest_actions(
                intent_result, emotion_result, knowledge_result, 
                customer_data=customer_data, history=history
            ))

            suggestions = await suggestions_task
            if isinstance(suggestions, Exception):
                app_logger.error(f"Action Agent failed for {phone_number}: {str(suggestions)}")
                suggestions = []

            # Summary and QA results are not re-run here as they are automated separately
            summary_result = AgentResponse(
                agent_name="SummaryAgent",
                result={"summary": "Summary not re-generated during operator-triggered analysis. Check automated results."},
                confidence=0.0
            )
            qa_result = AgentResponse(
                agent_name="QAAgent",
                result={"feedback": "QA feedback not re-generated during operator-triggered analysis. Check automated results."},
                confidence=0.0
            )

            output = ProcessingResultOutput(
                phone_number=phone_number,
                intent=intent_result,
                emotion=emotion_result,
                knowledge=knowledge_result,
                suggestions=suggestions,
                summary=summary_result,
                qa_feedback=qa_result,
                consolidated_output=consolidated_output,
                conversation_history=history,
                history_storage_status=True,
                customer_data=customer_data,
                current_turn_id=history[-1].turn_id if history else None
            )
            app_logger.info(f"Orchestrator: Completed analysis for customer {phone_number}")
            return output

    except asyncio.TimeoutError as e:
        app_logger.error(f"Timeout during agent analysis for customer {phone_number} after {timeout_seconds}s")
        return ProcessingResultOutput(
            phone_number=phone_number,
            consolidated_output=f"Ошибка: истекло время ожидания анализа ({timeout_seconds} сек)",
            customer_data=None
        )
    except Exception as e:
        app_logger.error(f"Analysis orchestration failed for customer {phone_number}: {e}")
        return ProcessingResultOutput(
            phone_number=phone_number,
            consolidated_output=f"Ошибка анализа: {str(e)}",
            customer_data=None
        )
