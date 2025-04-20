import json
from typing import List, Optional
from app.models.schemas import AgentResponse, HistoryEntry
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def summarize_conversation(history: List[HistoryEntry], latest_user_text: Optional[str] = None) -> AgentResponse:
    """
    Summarize a batch of conversation history into a concise overview for the operator.
    Uses history context and optionally the latest user message to generate a summary in Russian.
    Handles LLM response parsing failures with fallback logic.
    """
    settings = get_settings()
    app_logger.info(f"Summary Agent: Summarizing conversation with {len(history)} turns")
    
    # Build conversation context from history
    history_context = ""
    if history and len(history) > 0:
        history_texts = []
        for i, turn in enumerate(history[-5:], 1):  # Limit to last 5 turns for brevity
            user_text = turn.user_text if turn.user_text else "Не указано"
            op_response = turn.operator_response if turn.operator_response else "Ответ оператора отсутствует"
            history_texts.append(f"Сообщение {i}: Клиент: '{user_text}' | Оператор: '{op_response}'")
        history_context = f"""
        История диалога (последние {len(history_texts)} сообщений):
        {'; '.join(history_texts)}
        Используйте историю для создания полного резюме беседы.
        """
    else:
        history_context = "История диалога отсутствует. Создайте резюме только на основе текущего сообщения, если оно доступно."

    # Include latest user text if provided
    latest_text_context = ""
    if latest_user_text:
        latest_text_context = f"Последнее сообщение клиента: '{latest_user_text}'"
        app_logger.debug(f"Summary Agent: Including latest user text: {latest_user_text[:50]}...")
    else:
        app_logger.debug("Summary Agent: No latest user text provided, summarizing based on history only.")

    # Construct prompt for summarizing conversation history
    prompt = f"""
    Вы - ассистент контакт-центра, специализирующийся на создании кратких резюме диалогов.
    Ваша задача - проанализировать историю диалога и/или последнее сообщение клиента и создать краткое резюме на русском языке.
    Резюме должно содержать ключевые моменты беседы (например, основные проблемы, запросы клиента, решения).
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Пример ответа:
    {{
        "summary": "Клиент пожаловался на проблему с интернетом, оператор предложил перезагрузить роутер.",
        "confidence": 0.9
    }}
    {history_context}
    {latest_text_context if latest_text_context else 'Последнее сообщение клиента отсутствует.'}
    """
    try:
        app_logger.debug(f"Summary Agent: Sending prompt to LLM for conversation summary.")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.SUMMARY_MODEL,
            temperature=0.3  # Low temperature for factual summaries
        )
        
        if not response:
            app_logger.error("Summary Agent: No response received from LLM")
            return AgentResponse(
                agent_name="SummaryAgent",
                result={"summary": "Не удалось сгенерировать резюме.", "confidence": 0.0},
                error="No response from LLM"
            )

        app_logger.debug(f"Summary Agent: Raw LLM response: {response[:200]}...")
        
        # Parse JSON response, handling potential markdown formatting
        try:
            response_cleaned = response.strip().replace("```json", "").replace("```", "")
            result = json.loads(response_cleaned)
            
            summary = result.get("summary", "Не удалось сгенерировать резюме.")
            confidence = result.get("confidence", 0.0)
            
            app_logger.info(f"Summary Agent: Generated summary with confidence {confidence}")
            return AgentResponse(
                agent_name="SummaryAgent",
                result={"summary": summary, "confidence": confidence},
                confidence=confidence
            )
        except json.JSONDecodeError as jde:
            app_logger.warning(f"Summary Agent: Failed to parse JSON from LLM response: {response[:100]}... Error: {str(jde)}")
            return AgentResponse(
                agent_name="SummaryAgent",
                result={"summary": "Не удалось сгенерировать резюме из-за ошибки формата.", "confidence": 0.3},
                confidence=0.3,
                error=f"Failed to parse JSON: {str(jde)}"
            )
    except Exception as e:
        app_logger.error(f"Summary Agent: Unexpected error during summary generation: {str(e)}")
        return AgentResponse(
            agent_name="SummaryAgent",
            result={"summary": "Не удалось сгенерировать резюме из-за ошибки.", "confidence": 0.0},
            confidence=0.0,
            error=f"Unexpected error: {str(e)}"
        )
