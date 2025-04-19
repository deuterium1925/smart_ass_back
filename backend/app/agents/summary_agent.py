from app.models.schemas import AgentResponse
from app.utils.logger import app_logger

async def summarize_turn(text: str, intent_result: AgentResponse, emotion_result: AgentResponse, knowledge_result: AgentResponse) -> AgentResponse:
    """
    Placeholder for summarizing the current conversation turn.
    """
    app_logger.debug(f"Summarizing conversation turn for text: {text[:50]}...")
    intent = intent_result.result.get("intent", "unknown") if isinstance(intent_result.result, dict) else "unknown"
    emotion = emotion_result.result.get("emotion", "unknown") if isinstance(emotion_result.result, dict) else "unknown"
    return AgentResponse(
        agent_name="SummaryAgent",
        result={"summary": f"Клиент выразил намерение: {intent}, эмоция: {emotion}."},
        confidence=0.7
    )
