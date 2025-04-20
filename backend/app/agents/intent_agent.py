import json
from typing import Dict, Any, List, Optional
from app.models.schemas import AgentResponse, HistoryEntry
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def detect_intent(text: str, history: Optional[List[HistoryEntry]] = None) -> AgentResponse:
    """
    Detect the intent of a user's message or batch of messages using the MWS GPT API, leveraging conversation history for context.
    Accepts concatenated text from multiple messages for batch processing.
    Returns an AgentResponse with the detected intent and confidence score for operator guidance.
    Includes fallback logic to handle LLM response parsing failures.
    """
    settings = get_settings()
    # Predefined intent categories for classification and fallback
    possible_intents = [
        "billing_issue", "technical_support", "complaint", "product_info", "other"
    ]
    
    # Incorporate conversation history if available to improve intent accuracy
    history_context = ""
    if history and len(history) > 0:
        app_logger.debug(f"Intent Agent: Incorporating history with {len(history)} turns for text: {text[:50]}")
        history_texts = []
        for turn in history[-5:]:  # Limit to last 5 turns to manage token usage
            user_text = turn.user_text if turn.user_text else "Не указано"
            op_response = turn.operator_response if turn.operator_response else "Ответ оператора отсутствует"
            history_texts.append(f"Клиент: {user_text} | Оператор: {op_response}")
        history_context = f"""
        История диалога (последние {len(history_texts)} сообщений):
        {'; '.join(history_texts)}
        Учитывайте историю для более точного определения намерения.
        """
    else:
        history_context = "История диалога отсутствует. Определяйте намерение только на основе текущего сообщения."

    # Construct a structured prompt for precise intent detection in Russian, supporting batch analysis
    prompt = f"""
    Вы - ассистент контакт-центра, специализирующийся на определении намерений клиента.
    Ваша задача - проанализировать сообщение или набор сообщений клиента на русском языке и определить основное намерение.
    Учитывайте историю диалога, если она доступна, чтобы понять контекст общения.
    Если предоставлен набор сообщений, определите общее намерение, объединяющее их содержание.
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Если намерение неясно, используйте категорию "other".
    Пример ответа:
    {{
        "intent": "billing_issue",
        "confidence": 0.92
    }}
    Возможные категории намерений: {', '.join(possible_intents)}.
    {history_context}
    Сообщение(я) клиента для анализа: "{text}"
    """
    try:
        app_logger.debug(f"Intent Agent: Sending prompt to LLM for text: {text[:50]}...")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.INTENT_MODEL,
            temperature=0.2  # Low temperature for deterministic JSON output
        )
        
        if not response:
            app_logger.error("Intent Agent: No response received from LLM")
            return AgentResponse(
                agent_name="IntentAgent",
                result={"intent": "unknown", "confidence": 0.0},
                error="No response from LLM"
            )

        app_logger.debug(f"Intent Agent: Raw LLM response: {response[:200]}...")
        
        # Parse JSON response, handling potential markdown formatting
        try:
            response_cleaned = response.strip().replace("```json", "").replace("```", "")
            result = json.loads(response_cleaned)
            
            intent = result.get("intent", "unknown")
            confidence = result.get("confidence", 0.0)
            
            # Validate detected intent against predefined categories
            if intent not in possible_intents:
                app_logger.warning(f"Intent Agent: Invalid intent '{intent}' detected, defaulting to 'other'")
                intent = "other"
                confidence = 0.5  # Moderate confidence for fallback
            
            app_logger.info(f"Intent Agent: Detected intent '{intent}' with confidence {confidence} for text: {text[:50]}")
            return AgentResponse(
                agent_name="IntentAgent",
                result={"intent": intent, "confidence": confidence},
                confidence=confidence
            )
        except json.JSONDecodeError as jde:
            app_logger.warning(f"Intent Agent: Failed to parse JSON from LLM response: {response[:100]}... Error: {str(jde)}")
            # Fallback to keyword search in response for intent estimation
            response_lower = response.lower()
            fallback_intent = "other"
            fallback_confidence = 0.3  # Low confidence for fallback
            
            for intent in possible_intents:
                if intent.replace("_", " ") in response_lower:
                    fallback_intent = intent
                    fallback_confidence = 0.6  # Higher confidence on keyword match
                    break
            
            app_logger.info(f"Intent Agent: Fallback intent '{fallback_intent}' with confidence {fallback_confidence} for text: {text[:50]}")
            return AgentResponse(
                agent_name="IntentAgent",
                result={"intent": fallback_intent, "confidence": fallback_confidence},
                confidence=fallback_confidence,
                error=f"Failed to parse JSON: {str(jde)}"
            )
    except Exception as e:
        app_logger.error(f"Intent Agent: Unexpected error during intent detection for text '{text[:50]}...': {str(e)}")
        return AgentResponse(
            agent_name="IntentAgent",
            result={"intent": "unknown", "confidence": 0.0},
            confidence=0.0,
            error=f"Unexpected error: {str(e)}"
        )
