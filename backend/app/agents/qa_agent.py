import json
from app.models.schemas import AgentResponse
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def check_quality(user_text: str, operator_response: str) -> AgentResponse:
    """
    Evaluates the quality of the operator's response based on predefined communication standards.
    Uses an LLM to analyze tone, clarity, empathy, and adherence to guidelines in the context
    of the user's message. Returns feedback and a confidence score to guide operator improvement.
    Includes fallback logic for handling LLM failures. Only triggered after operator response.
    """
    settings = get_settings()
    app_logger.info(f"QA Agent: Evaluating operator response for user text: {user_text[:50]}...")

    # Construct a structured prompt for quality assurance evaluation in Russian
    prompt = f"""
    Вы - ассистент контакт-центра, специализирующийся на проверке качества ответов операторов.
    Ваша задача - проанализировать ответ оператора на сообщение клиента и оценить его по следующим критериям:
    1. Профессионализм (формальность, корректность тона)
    2. Ясность и полнота ответа (понятность, соответствие запросу клиента)
    3. Эмпатия (учет эмоционального состояния клиента)
    4. Соблюдение стандартов общения (отсутствие грубости, использование стандартных фраз приветствия/прощания, если применимо)
    Ответ должен быть строго в формате JSON, как в примере ниже. Не добавляйте лишний текст или пояснения.
    Включите конкретные замечания или рекомендации, если есть проблемы, либо подтверждение соответствия стандартам.
    Пример ответа:
    {{
        "feedback": "Ответ оператора соответствует стандартам общения. Тон профессиональный, ответ полный и учитывает запрос клиента.",
        "confidence": 0.85
    }}
    Сообщение клиента: "{user_text}"
    Ответ оператора: "{operator_response if operator_response else 'Ответ оператора отсутствует.'}"
    Оцените качество ответа оператора:
    """

    try:
        app_logger.debug(f"QA Agent: Sending prompt to LLM for quality check.")
        response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.QA_MODEL,
            temperature=0.3  # Low temperature for factual and structured feedback
        )
        
        if not response:
            app_logger.error("QA Agent: No response received from LLM")
            return AgentResponse(
                agent_name="QAAgent",
                result={"feedback": "Не удалось оценить качество ответа из-за отсутствия ответа от модели.", "confidence": 0.0},
                confidence=0.0,
                error="No response from LLM"
            )

        app_logger.debug(f"QA Agent: Raw LLM response: {response[:200]}...")
        
        # Parse JSON response, handling potential markdown formatting
        try:
            response_cleaned = response.strip().replace("```json", "").replace("```", "")
            result = json.loads(response_cleaned)
            
            feedback = result.get("feedback", "Не удалось оценить качество ответа.")
            confidence = result.get("confidence", 0.5)
            
            app_logger.info(f"QA Agent: Generated feedback with confidence {confidence}")
            return AgentResponse(
                agent_name="QAAgent",
                result={"feedback": feedback, "confidence": confidence},
                confidence=confidence
            )
        except json.JSONDecodeError as jde:
            app_logger.warning(f"QA Agent: Failed to parse JSON from LLM response: {response[:100]}... Error: {str(jde)}")
            return AgentResponse(
                agent_name="QAAgent",
                result={"feedback": "Не удалось оценить качество ответа из-за ошибки формата данных.", "confidence": 0.3},
                confidence=0.3,
                error=f"Failed to parse JSON: {str(jde)}"
            )
    except Exception as e:
        app_logger.error(f"QA Agent: Unexpected error during quality check: {str(e)}")
        # Fallback feedback based on basic heuristics if possible
        fallback_feedback = "Не удалось оценить качество ответа из-за технической ошибки."
        fallback_confidence = 0.0
        
        # Basic heuristic check if operator response is empty or very short
        if not operator_response or len(operator_response.strip()) < 10:
            fallback_feedback = "Ответ оператора отсутствует или слишком короткий. Рекомендуется предоставить более развернутый ответ."
            fallback_confidence = 0.5
        
        return AgentResponse(
            agent_name="QAAgent",
            result={"feedback": fallback_feedback, "confidence": fallback_confidence},
            confidence=fallback_confidence,
            error=f"Unexpected error: {str(e)}"
        )
