import json
from typing import List, Optional
from app.models.schemas import AgentResponse, HistoryEntry
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def detect_emotion(text: str, history: Optional[List[HistoryEntry]] = None) -> AgentResponse:
    """
    Detect the emotional tone of a user's message using the MWS GPT API, using history for context.
    Returns an AgentResponse with the detected emotion and confidence score to aid operator response.
    Handles LLM response parsing failures with fallback logic.
    """
    settings = get_settings()
    # Predefined emotion categories for classification and fallback
    possible_emotions = [
        "neutral", "positive", "negative", "angry", "frustrated", "happy", "sad", "confused"
    ]
    
    # Incorporate conversation history if available for better emotional context
    history_context = ""
    if history and len(history) > 0:
        app_logger.debug(f"Emotion Agent: Incorporating history with {len(history)} turns for text: {text[:50]}")
        history_texts = []
        for turn in history[-3:]:  # Limit to last 3 turns to manage token usage
            user_text = turn.user_text if turn.user_text else "Не указано"
            op_response = turn.operator_response if turn.operator_response else "Ответ оператора отсутствует"
            history_texts.append(f"Клиент: {user_text} | Оператор: {op_response}")
        history_context = f"""
        История диалога (последние {len(history_texts)} сообщений):
        {'; '.join(history_texts)}
        Учитывайте историю для более точного определения эмоционального тона.
        """
    else:
        history_context = "История диалога отсутствует. Определяйте эмоцию только на основе текущего сообщения."

    # Construct a structured prompt for precise emotion detection in Russian
    prompt = f"""
    Вы - ассистент контакт-центра, специализирующийся на анализе эмоциональной окраски сообщений клиентов.
    Ваша задача - проанализировать сообщение клиента на русском языке и определить его эмоциональный тон.
    Учитывайте историю диалога, если она доступна, чтобы понять контекст общения (например, нарастающее раздражение).
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Если эмоция неясна, используйте категорию "neutral".
    Пример ответа:
    {{
        "emotion": "angry",
        "confidence": 0.85
    }}
    Возможные категории эмоций: {', '.join(possible_emotions)}.
    {history_context}
    Сообщение клиента для анализа: "{text}"
    """
    try:
        app_logger.debug(f"Emotion Agent: Sending prompt to LLM for text: {text[:50]}...")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.EMOTION_MODEL,
            temperature=0.2  # Low temperature for deterministic JSON output
        )
        
        if not response:
            app_logger.error("Emotion Agent: No response received from LLM")
            return AgentResponse(
                agent_name="EmotionAgent",
                result={"emotion": "neutral", "confidence": 0.0},
                error="No response from LLM"
            )

        app_logger.debug(f"Emotion Agent: Raw LLM response: {response[:200]}...")
        
        # Parse JSON response, handling potential markdown formatting
        try:
            response_cleaned = response.strip().replace("```json", "").replace("```", "")
            result = json.loads(response_cleaned)
            
            emotion = result.get("emotion", "neutral")
            confidence = result.get("confidence", 0.0)
            
            # Validate detected emotion against predefined categories
            if emotion not in possible_emotions:
                app_logger.warning(f"Emotion Agent: Invalid emotion '{emotion}' detected, defaulting to 'neutral'")
                emotion = "neutral"
                confidence = 0.5  # Moderate confidence for fallback
            
            app_logger.info(f"Emotion Agent: Detected emotion '{emotion}' with confidence {confidence} for text: {text[:50]}")
            return AgentResponse(
                agent_name="EmotionAgent",
                result={"emotion": emotion, "confidence": confidence},
                confidence=confidence
            )
        except json.JSONDecodeError as jde:
            app_logger.warning(f"Emotion Agent: Failed to parse JSON from LLM response: {response[:100]}... Error: {str(jde)}")
            # Fallback to keyword search in response for emotion estimation
            response_lower = response.lower()
            fallback_emotion = "neutral"
            fallback_confidence = 0.3  # Low confidence for fallback
            
            for emotion in possible_emotions:
                if emotion in response_lower:
                    fallback_emotion = emotion
                    fallback_confidence = 0.6  # Higher confidence on keyword match
                    break
            
            app_logger.info(f"Emotion Agent: Fallback emotion '{fallback_emotion}' with confidence {fallback_confidence} for text: {text[:50]}")
            return AgentResponse(
                agent_name="EmotionAgent",
                result={"emotion": fallback_emotion, "confidence": fallback_confidence},
                confidence=fallback_confidence,
                error=f"Failed to parse JSON: {str(jde)}"
            )
    except Exception as e:
        app_logger.error(f"Emotion Agent: Unexpected error during emotion detection for text '{text[:50]}...': {str(e)}")
        return AgentResponse(
            agent_name="EmotionAgent",
            result={"emotion": "neutral", "confidence": 0.0},
            confidence=0.0,
            error=f"Unexpected error: {str(e)}"
        )
