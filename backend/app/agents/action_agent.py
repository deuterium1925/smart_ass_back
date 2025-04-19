import json
from typing import List, Optional
from app.models.schemas import AgentResponse, Suggestion, Customer
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def suggest_actions(
    intent_response: AgentResponse,
    emotion_response: AgentResponse,
    knowledge_response: AgentResponse,
    customer_data: Optional[Customer] = None
) -> List[Suggestion]:
    """
    Suggest actionable responses for the operator based on intent, emotion, and knowledge results.
    Incorporates customer profile data (if available) for personalized suggestions.
    Returns a list of Suggestion objects with Russian text.
    """
    settings = get_settings()
    intent = intent_response.result.get("intent", "unknown")
    intent_confidence = intent_response.confidence or 0.0
    emotion = emotion_response.result.get("emotion", "unknown")
    emotion_confidence = emotion_response.confidence or 0.0
    
    app_logger.info(f"Action Agent: Generating suggestions for intent={intent}, emotion={emotion}")

    # Build customer context for prompt if data is available
    customer_context = ""
    if customer_data:
        app_logger.debug(f"Incorporating customer data for {customer_data.phone_number} into suggestions")
        customer_context = f"""
        Информация о клиенте:
        - Абонент МТС: {'Да' if customer_data.is_mts_subscriber else 'Нет'}
        - Тарифный план: {customer_data.tariff_plan or 'Не указан'}
        - Подписка MTS Premium: {'Да' if customer_data.has_mts_premium else 'Нет'}
        - Подписка MTS Cashback: {'Да' if customer_data.has_mts_cashback else 'Нет'}
        - Использует приложение Мой МТС: {'Да' if customer_data.uses_my_mts_app else 'Нет'}
        - Услуги: {'Мобильная связь' if customer_data.has_mobile else ''}, {'Домашний интернет' if customer_data.has_home_internet else ''}, {'Домашнее ТВ' if customer_data.has_home_tv else ''}
        Учитывайте эту информацию для персонализированных предложений, например, предложите скидку или бонусы для пользователей MTS Premium.
        """
    else:
        app_logger.debug("No customer data provided, using generic suggestion logic")
        customer_context = "Информация о клиенте отсутствует. Используйте общие рекомендации без персонализации."

    # Craft a structured prompt with customer context for better suggestion quality
    prompt = f"""
    Вы - ассистент контакт-центра, помогающий оператору выбрать подходящие действия для клиента.
    Ваша задача - предложить 1-3 конкретных действия или ответа для оператора на основе намерения клиента, его эмоций и информации из базы знаний.
    Учитывайте информацию о клиенте для персонализированных предложений, если она доступна.
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Все предложения должны быть на русском языке.
    Пример ответа:
    [
        {{
            "text": "Предложите клиенту скидку 10% на следующий месяц.",
            "type": "discount_offer",
            "priority": 2
        }},
        {{
            "text": "Помогите клиенту решить проблему с подключением.",
            "type": "problem_resolution",
            "priority": 1
        }}
    ]

    Намерение клиента: {intent} (уверенность: {intent_confidence})
    Эмоциональное состояние клиента: {emotion} (уверенность: {emotion_confidence})
    {customer_context}
    Предложите действия для оператора:
    """

    try:
        app_logger.debug(f"Action Agent: Sending prompt to LLM for intent={intent}, emotion={emotion}")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.ACTION_MODEL,
            temperature=0.5  # Moderate temperature for structured yet creative output
        )
        
        if not response:
            app_logger.error("Action Agent: No response received from LLM")
            return []

        app_logger.debug(f"Action Agent: Raw LLM response: {response[:200]}...")
        
        # Clean response by removing markdown code blocks if present
        response_cleaned = response.strip().replace("```json", "").replace("```", "")
        try:
            suggestions_data = json.loads(response_cleaned)
            if not isinstance(suggestions_data, list):
                app_logger.error(f"Action Agent: Expected list of suggestions, got {type(suggestions_data)}")
                return []

            suggestions = []
            for item in suggestions_data:
                try:
                    suggestion = Suggestion(
                        text=item.get("text", ""),
                        type=item.get("type", "general"),
                        priority=item.get("priority", 1)
                    )
                    suggestions.append(suggestion)
                except Exception as e:
                    app_logger.warning(f"Action Agent: Invalid suggestion format in response: {item}, error: {str(e)}")

            app_logger.info(f"Action Agent: Generated {len(suggestions)} valid suggestions for intent={intent}")
            return suggestions
        except json.JSONDecodeError as jde:
            app_logger.error(f"Action Agent: Failed to parse JSON from LLM response: {response[:100]}... Error: {str(jde)}")
            return []
    except Exception as e:
        app_logger.error(f"Action Agent: Unexpected error during suggestion generation: {str(e)}")
        return []
