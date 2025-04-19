import json
from typing import Dict, Any
from app.models.schemas import AgentResponse
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def detect_intent(text: str) -> AgentResponse:
    """
    Detect the intent of the user's message using MWS GPT API.
    Returns an AgentResponse with the detected intent and confidence score.
    Includes fallback logic to handle malformed or unexpected LLM responses.
    """
    settings = get_settings()
    # Define possible intents for fallback classification if parsing fails
    possible_intents = [
        "billing_issue", "technical_support", "complaint", "product_info", "other"
    ]
    
    # Craft a detailed and structured prompt to improve response consistency
    prompt = f"""
    Вы - ассистент контакт-центра, специализирующийся на определении намерений клиента.
    Ваша задача - проанализировать сообщение клиента на русском языке и определить его основное намерение.
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Если намерение неясно, используйте категорию "other".
    Пример ответа:
    {{
        "intent": "billing_issue",
        "confidence": 0.92
    }}
    Возможные категории намерений: {', '.join(possible_intents)}.
    Сообщение клиента для анализа: "{text}"
    """
    try:
        app_logger.debug(f"Intent Agent: Sending prompt to LLM for text: {text[:50]}...")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.INTENT_MODEL,
            temperature=0.2  # Lower temperature for more deterministic JSON output
        )
        
        if not response:
            app_logger.error("Intent Agent: No response received from LLM")
            return AgentResponse(
                agent_name="IntentAgent",
                result={"intent": "unknown", "confidence": 0.0},
                error="No response from LLM"
            )

        app_logger.debug(f"Intent Agent: Raw LLM response: {response[:200]}...")
        
        # Attempt to parse JSON from the response
        try:
            # Handle cases where response might be wrapped in markdown code blocks
            response_cleaned = response.strip().replace("```json", "").replace("```", "")
            result = json.loads(response_cleaned)
            
            intent = result.get("intent", "unknown")
            confidence = result.get("confidence", 0.0)
            
            # Validate intent against possible values
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
            # Fallback: Search for keywords in the response text to guess intent
            response_lower = response.lower()
            fallback_intent = "other"
            fallback_confidence = 0.3  # Low confidence for fallback guess
            
            for intent in possible_intents:
                if intent.replace("_", " ") in response_lower:
                    fallback_intent = intent
                    fallback_confidence = 0.6  # Slightly higher confidence if keyword match
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
