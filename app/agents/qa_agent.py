from app.models.schemas import AgentResponse
from app.utils.logger import app_logger

async def check_quality(user_text: str, operator_response: str) -> AgentResponse:
    """
    Placeholder for quality assurance check on operator's response.
    """
    app_logger.debug("Performing quality assurance check...")
    return AgentResponse(
        agent_name="QAAgent",
        result={"feedback": "Ответ оператора соответствует стандартам общения."},
        confidence=0.8
    )
