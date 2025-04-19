# app/models/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Customer(BaseModel):
    phone_number: str = Field(..., description="Unique identifier for the customer (e.g., '8-916-999-99-99')")
    is_mts_subscriber: bool = Field(default=False, description="Whether the customer is an MTS subscriber")
    tariff: str = Field(default="", description="Tariff plan (e.g., 'Convergent Tariff Plan №7')")
    mobile_service: bool = Field(default=False, description="Has mobile service")
    home_internet: bool = Field(default=False, description="Has home internet")
    home_tv: bool = Field(default=False, description="Has home TV")
    home_phone: bool = Field(default=False, description="Has home phone")
    device: str = Field(default="", description="Device used (e.g., 'iPhone 16 Pro 256 GB')")
    os: str = Field(default="", description="Operating system and version (e.g., 'iOS 18.4')")
    is_my_mts_app_user: bool = Field(default=False, description="Uses My MTS app")
    is_personal_cabinet_user: bool = Field(default=False, description="Uses Personal Cabinet")
    is_mts_bank_app_user: bool = Field(default=False, description="Uses MTS Bank app")
    is_mts_money_app_user: bool = Field(default=False, description="Uses MTS Money app")
    subscriptions: str = Field(default="none", description="Active subscriptions on the number")
    mts_premium: bool = Field(default=False, description="Has MTS Premium")
    mts_cashback: bool = Field(default=False, description="Has MTS Cashback")
    protector_basic: bool = Field(default=False, description="Has Protector Basic")
    protector_plus: bool = Field(default=False, description="Has Protector Plus")
    kion_subscription: bool = Field(default=False, description="Has separate Kion subscription")
    music_subscription: bool = Field(default=False, description="Has separate Music subscription")
    strings_subscription: bool = Field(default=False, description="Has separate Strings subscription")
    mts_bank_debit_card: bool = Field(default=False, description="Has MTS Bank debit card")
    mts_bank_credit_card: bool = Field(default=False, description="Has MTS Bank credit card")
    mts_money_debit_card: bool = Field(default=False, description="Has MTS Money debit card")
    mts_money_credit_card: bool = Field(default=False, description="Has MTS Money credit card")
    mts_money_virtual_card: bool = Field(default=False, description="Has MTS Money virtual card")
    created_at: str = Field(default="", description="Timestamp of customer creation")

class HistoryEntry(BaseModel):
    user_text: str = Field(default="", description="Text from the user.")
    operator_response: str = Field(default="", description="Response from the operator.")
    timestamp: str = Field(default="", description="Timestamp of the conversation turn.")
    role: str = Field(default="unknown", description="Role of the speaker (user/assistant/unknown).")

class UserMessageInput(BaseModel):
    phone_number: str = Field(..., description="Unique identifier for the customer.")  # Replaced session_id
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
    phone_number: str = Field(..., description="Unique identifier for the customer.")  # Replaced session_id
    intent: Optional[AgentResponse] = Field(default=None, description="Intent detection result.")
    emotion: Optional[AgentResponse] = Field(default=None, description="Emotion analysis result.")
    knowledge: Optional[AgentResponse] = Field(default=None, description="Knowledge retrieval result.")
    suggestions: List[Suggestion] = Field(default=[], description="List of suggestions for the operator.")
    summary: Optional[AgentResponse] = Field(default=None, description="Summary of the conversation turn.")
    qa_feedback: Optional[AgentResponse] = Field(default=None, description="Quality assurance feedback.")
    consolidated_output: Optional[str] = Field(
        default=None, description="Consolidated summary of processing for quick reference."
    )
    conversation_history: Optional[List[HistoryEntry]] = Field(
        default=None, description="Recent conversation history for the customer."
    )
    history_storage_status: Optional[bool] = Field(
        default=True, description="Status of storing the current conversation turn to history."
    )
    customer_data: Optional[Customer] = Field(
        default=None, description="Customer profile data associated with the phone number."
    )