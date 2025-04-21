import json
from typing import List, Optional
from app.models.schemas import AgentResponse, Suggestion, Customer, HistoryEntry
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def suggest_actions(
    intent_response: AgentResponse,
    emotion_response: AgentResponse,
    knowledge_response: AgentResponse,
    customer_data: Optional[Customer] = None,
    history: Optional[List[HistoryEntry]] = None
) -> List[Suggestion]:
    """
    Suggest three distinct actionable responses for the operator based on intent, emotion, knowledge,
    customer profile, and conversation history. Ensures personalized, prioritized suggestions in Russian
    for real-time contact center support. Returns a list of Suggestion objects.
    """
    settings = get_settings()
    intent = intent_response.result.get("intent", "unknown")
    intent_confidence = intent_response.confidence or 0.0
    emotion = emotion_response.result.get("emotion", "neutral")
    emotion_confidence = emotion_response.confidence or 0.0
    
    # Extract knowledge content if available, truncating for prompt brevity
    knowledge_content = ""
    if knowledge_response.result.get("knowledge"):
        knowledge_items = knowledge_response.result.get("knowledge", [])
        if knowledge_items:
            knowledge_content = knowledge_items[0].get("content", "")
            if len(knowledge_content) > 800:  # Limit to prevent token overflow
                knowledge_content = knowledge_content[:800] + "... (сокращено)"
        else:
            knowledge_content = "Информация из базы знаний отсутствует."
    else:
        knowledge_content = "Информация из базы знаний отсутствует."
    
    app_logger.info(f"Action Agent: Generating suggestions for intent={intent}, emotion={emotion}")

    # Build customer context for personalized suggestions
    customer_context = ""
    if customer_data:
        app_logger.debug(f"Incorporating customer data for {customer_data.phone_number} into suggestions")
        customer_context = f"""
        Информация о клиенте:
        - Абонент МТС: {'Да' if customer_data.is_mts_subscriber else 'Нет'}
        - Тарифный план: {customer_data.tariff_plan or 'Не указан'}
        - Подписка MTS Premium: {'Да' if customer_data.has_mts_premium else 'Нет'}
        - Использует приложение Мой МТС: {'Да' if customer_data.uses_my_mts_app else 'Нет'}
        - Услуги: {'Мобильная связь' if customer_data.has_mobile else ''}, {'Домашний интернет' if customer_data.has_home_internet else ''}, {'Домашнее ТВ' if customer_data.has_home_tv else ''}
        Учитывайте эту информацию для персонализированных предложений (например, скидки для абонентов МТС Premium).
        """
    else:
        app_logger.debug("No customer data provided, using generic suggestion logic")
        customer_context = "Информация о клиенте отсутствует. Используйте общие рекомендации без персонализации."

    # Build history context to avoid repetitive suggestions and enhance relevance
    history_context = ""
    if history and len(history) > 0:
        app_logger.debug(f"Incorporating conversation history with {len(history)} turns into suggestions")
        history_texts = []
        for i, turn in enumerate(history[-3:], 1):  # Limit to last 3 turns for brevity
            user_text = turn.user_text if turn.user_text else "Не указано"
            op_response = turn.operator_response if turn.operator_response else "Ответ оператора отсутствует"
            history_texts.append(f"Сообщение {i}: Клиент: '{user_text}' | Оператор: '{op_response}'")
        history_context = f"""
        История диалога (последние {len(history_texts)} сообщений):
        {'; '.join(history_texts)}
        Учитывайте историю, чтобы избежать повторяющихся предложений и учитывать предыдущие действия.
        """
    else:
        app_logger.debug("No conversation history provided, proceeding without historical context")
        history_context = "История диалога отсутствует. Базируйте предложения только на текущем сообщении."

    # Construct a structured prompt for generating diverse, prioritized suggestions
    prompt = f"""
    Вы - ассистент контакт-центра, помогающий оператору выбрать подходящие действия для общения с клиентом.
    Ваша задача - предложить ровно 3 конкретных, разнообразных действия или ответа для оператора на основе:
    1. Намерения клиента
    2. Эмоционального состояния клиента
    3. Информации из базы знаний
    4. Персональных данных клиента (если доступны)
    5. Истории диалога (если доступна)
    Убедитесь, что предложения отличаются друг от друга по подходу (например, решение проблемы, предложение скидки, уточнение деталей)
    и имеют разный уровень приоритета (1 - высокий, 2 - средний, 3 - низкий).
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Все предложения должны быть на русском языке.
    Пример ответа:
    [
        {{
            "text": "Предложите клиенту скидку 10% на следующий месяц для успокоения.",
            "type": "discount_offer",
            "priority": 2
        }},
        {{
            "text": "Помогите клиенту решить проблему с подключением интернета, следуя инструкциям из базы знаний.",
            "type": "problem_resolution",
            "priority": 1
        }},
        {{
            "text": "Уточните у клиента дополнительные детали о проблеме для более точного решения.",
            "type": "clarification_request",
            "priority": 3
        }}
    ]

    Намерение клиента: {intent} (уверенность: {intent_confidence})
    Эмоциональное состояние клиента: {emotion} (уверенность: {emotion_confidence})
    Информация из базы знаний: {knowledge_content}
    {customer_context}
    {history_context}
    Предложите ровно 3 действия для оператора в указанном формате:
    """

    try:
        app_logger.debug(f"Action Agent: Sending prompt to LLM for intent={intent}, emotion={emotion}")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.ACTION_MODEL,
            temperature=0.6  # Moderate temperature for creative yet structured output
        )
        
        if not response:
            app_logger.error("Action Agent: No response received from LLM")
            return fallback_suggestions(intent, emotion)

        app_logger.debug(f"Action Agent: Raw LLM response: {response[:200]}...")
        
        # Clean and parse JSON response, removing markdown if present
        response_cleaned = response.strip().replace("```json", "").replace("```", "")
        try:
            suggestions_data = json.loads(response_cleaned)
            if not isinstance(suggestions_data, list):
                app_logger.error(f"Action Agent: Expected list of suggestions, got {type(suggestions_data)}")
                return fallback_suggestions(intent, emotion)

            suggestions = []
            for item in suggestions_data:
                try:
                    suggestion = Suggestion(
                        text=item.get("text", ""),
                        type=item.get("type", "general"),
                        priority=item.get("priority", 1)
                    )
                    if suggestion.text:  # Add only if text is non-empty
                        suggestions.append(suggestion)
                except Exception as e:
                    app_logger.warning(f"Action Agent: Invalid suggestion format in response: {item}, error: {str(e)}")

            # Ensure exactly 3 suggestions, using fallback if needed
            if len(suggestions) != 3:
                app_logger.warning(f"Action Agent: Expected 3 suggestions, got {len(suggestions)}. Using fallback to complete.")
                fallback = fallback_suggestions(intent, emotion)
                while len(suggestions) < 3 and fallback:
                    # Add unique fallback suggestions not already present
                    fb = fallback.pop(0)
                    if not any(s.text == fb.text for s in suggestions):
                        suggestions.append(fb)
                # Log if still less than 3 suggestions
                if len(suggestions) < 3:
                    app_logger.error(f"Action Agent: Could not generate 3 suggestions even with fallback. Returning {len(suggestions)} suggestions.")
            
            app_logger.info(f"Action Agent: Generated {len(suggestions)} valid suggestions for intent={intent}")
            return suggestions[:3]  # Ensure no more than 3 suggestions
        except json.JSONDecodeError as jde:
            app_logger.error(f"Action Agent: Failed to parse JSON from LLM response: {response[:100]}... Error: {str(jde)}")
            return fallback_suggestions(intent, emotion)
    except Exception as e:
        app_logger.error(f"Action Agent: Unexpected error during suggestion generation: {str(e)}")
        return fallback_suggestions(intent, emotion)

def fallback_suggestions(intent: str, emotion: str) -> List[Suggestion]:
    """
    Generate fallback suggestions based on intent and emotion when LLM fails.
    Returns up to 3 Suggestion objects tailored to contact center scenarios.
    """
    app_logger.info(f"Action Agent: Using fallback suggestions for intent={intent}, emotion={emotion}")
    suggestions = []
    
    # Emotion-based suggestion for handling customer sentiment
    if emotion in ["angry", "frustrated", "negative"]:
        suggestions.append(Suggestion(
            text="Предложите клиенту компенсацию или скидку для смягчения негативных эмоций.",
            type="compensation_offer",
            priority=1
        ))
    else:
        suggestions.append(Suggestion(
            text="Поблагодарите клиента за обращение и предложите помощь в решении вопроса.",
            type="general_assistance",
            priority=2
        ))

    # Intent-based suggestion for targeted problem resolution
    if intent == "billing_issue":
        suggestions.append(Suggestion(
            text="Проверьте состояние счета клиента и предложите варианты оплаты или скидку.",
            type="billing_resolution",
            priority=1
        ))
    elif intent == "technical_support":
        suggestions.append(Suggestion(
            text="Предложите пошаговую инструкцию для устранения технической проблемы.",
            type="technical_solution",
            priority=1
        ))
    elif intent == "complaint":
        suggestions.append(Suggestion(
            text="Извинитесь за неудобства и предложите эскалацию вопроса менеджеру.",
            type="complaint_handling",
            priority=1
        ))
    else:
        suggestions.append(Suggestion(
            text="Уточните детали запроса клиента для более точного решения.",
            type="clarification_request",
            priority=3
        ))

    # Add a generic follow-up if fewer than 3 suggestions
    if len(suggestions) < 3:
        suggestions.append(Suggestion(
            text="Спросите клиента, есть ли дополнительные вопросы или проблемы, которые нужно решить.",
            type="follow_up",
            priority=3
        ))

    return suggestions[:3]
