from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class UserMessageInput(BaseModel):
    session_id: str = Field(..., description="Unique identifier for the conversation session.")
    user_text: str = Field(..., description="The latest message from the user in Russian.")
    history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Previous conversation turns for context."
    )
    operator_response: Optional[str] = Field(
        default="", description="Latest response from the operator, if available."
    )

class AgentResponse(BaseModel):
    agent_name: str = Field(..., description="Name of the agent providing the response.")
    result: Any = Field(..., description="Result or analysis from the agent.")
    confidence: Optional[float] = Field(default=None, description="Confidence score for the result.")
    error: Optional[str] = Field(default=None, description="Error message if processing failed.")

class Suggestion(BaseModel):
    text: str = Field(..., description="Suggested action or response for the operator in Russian.")
    type: str = Field(..., description="Type of suggestion (e.g., 'discount_offer', 'problem_resolution').")
    priority: Optional[int] = Field(default=1, description="Priority level of the suggestion (1-5).")

class KnowledgeResult(BaseModel):
    document_id: str = Field(..., description="ID of the retrieved document.")
    content: str = Field(..., description="Relevant content snippet from the knowledge base.")
    relevance_score: float = Field(..., description="Relevance score for the document.")

class ProcessingResultOutput(BaseModel):
    session_id: str = Field(..., description="Unique identifier for the conversation session.")
    intent: Optional[AgentResponse] = Field(default=None, description="Intent detection result.")
    emotion: Optional[AgentResponse] = Field(default=None, description="Emotion analysis result.")
    knowledge: Optional[AgentResponse] = Field(default=None, description="Knowledge retrieval result.")
    suggestions: List[Suggestion] = Field(default=[], description="List of suggestions for the operator.")
    summary: Optional[AgentResponse] = Field(default=None, description="Summary of the conversation turn.")
    qa_feedback: Optional[AgentResponse] = Field(default=None, description="Quality assurance feedback.")
    consolidated_output: Optional[str] = Field(
        default=None, description="Consolidated summary of processing for quick reference."
    )
