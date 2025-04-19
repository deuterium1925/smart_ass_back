from app.models.schemas import AgentResponse
from app.utils.logger import app_logger

async def detect_emotion(text: str) -> AgentResponse:
    """
    Placeholder for detecting the emotion of the user's message.
    """
    app_logger.debug(f"Detecting emotion for text: {text[:50]}...")
    return AgentResponse(
        agent_name="EmotionAgent",
        result={"emotion": "neutral", "confidence": 0.5},
        confidence=0.5
    )
