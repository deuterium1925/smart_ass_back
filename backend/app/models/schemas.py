from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Customer(BaseModel):
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number).")
    is_mts_subscriber: bool = Field(default=False, description="Whether the customer is an MTS subscriber.")
    tariff_plan: Optional[str] = Field(default=None, description="Tariff plan of the customer (e.g., convergent plan).")
    has_mobile: bool = Field(default=False, description="Whether the customer has mobile services.")
    has_home_internet: bool = Field(default=False, description="Whether the customer has home internet.")
    has_home_tv: bool = Field(default=False, description="Whether the customer has home TV services.")
    has_home_phone: bool = Field(default=False, description="Whether the customer has a home phone.")
    device: Optional[str] = Field(default=None, description="Customer's device (e.g., iPhone 16 Pro 256 GB).")
    os: Optional[str] = Field(default=None, description="Operating system and version (e.g., iOS 18.4).")
    uses_my_mts_app: bool = Field(default=False, description="Whether the customer uses the My MTS app.")
    uses_personal_account: bool = Field(default=False, description="Whether the customer uses a personal account.")
    uses_mts_bank_app: bool = Field(default=False, description="Whether the customer uses the MTS Bank app.")
    uses_mts_money_app: bool = Field(default=False, description="Whether the customer uses the MTS Money app.")
    subscriptions_and_services: Optional[str] = Field(default=None, description="Subscriptions and services on the number.")
    has_mts_premium: bool = Field(default=False, description="Whether the customer has MTS Premium.")
    has_mts_cashback: bool = Field(default=False, description="Whether the customer has MTS Cashback.")
    has_defender_basic: bool = Field(default=False, description="Whether the customer has Defender Basic.")
    has_defender_plus: bool = Field(default=False, description="Whether the customer has Defender+.")
    has_kion_subscription: bool = Field(default=False, description="Whether the customer has a separate Kion subscription.")
    has_music_subscription: bool = Field(default=False, description="Whether the customer has a separate Music subscription.")
    has_strings_subscription: bool = Field(default=False, description="Whether the customer has a separate Strings subscription.")
    has_mts_bank_debit_card: bool = Field(default=False, description="Whether the customer has an MTS Bank debit card.")
    has_mts_bank_credit_card: bool = Field(default=False, description="Whether the customer has an MTS Bank credit card.")
    has_mts_money_debit_card: bool = Field(default=False, description="Whether the customer has an MTS Money debit card.")
    has_mts_money_credit_card: bool = Field(default=False, description="Whether the customer has an MTS Money credit card.")
    has_mts_money_virtual_card: bool = Field(default=False, description="Whether the customer has an MTS Money virtual card.")

class CustomerCreateRequest(BaseModel):
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number).")
    is_mts_subscriber: bool = Field(default=False, description="Whether the customer is an MTS subscriber.")
    tariff_plan: Optional[str] = Field(default=None, description="Tariff plan of the customer.")
    has_mobile: bool = Field(default=False, description="Whether the customer has mobile services.")
    has_home_internet: bool = Field(default=False, description="Whether the customer has home internet.")
    has_home_tv: bool = Field(default=False, description="Whether the customer has home TV services.")
    has_home_phone: bool = Field(default=False, description="Whether the customer has a home phone.")
    device: Optional[str] = Field(default=None, description="Customer's device.")
    os: Optional[str] = Field(default=None, description="Operating system and version.")
    uses_my_mts_app: bool = Field(default=False, description="Whether the customer uses the My MTS app.")
    uses_personal_account: bool = Field(default=False, description="Whether the customer uses a personal account.")
    uses_mts_bank_app: bool = Field(default=False, description="Whether the customer uses the MTS Bank app.")
    uses_mts_money_app: bool = Field(default=False, description="Whether the customer uses the MTS Money app.")
    subscriptions_and_services: Optional[str] = Field(default=None, description="Subscriptions and services on the number.")
    has_mts_premium: bool = Field(default=False, description="Whether the customer has MTS Premium.")
    has_mts_cashback: bool = Field(default=False, description="Whether the customer has MTS Cashback.")
    has_defender_basic: bool = Field(default=False, description="Whether the customer has Defender Basic.")
    has_defender_plus: bool = Field(default=False, description="Whether the customer has Defender+.")
    has_kion_subscription: bool = Field(default=False, description="Whether the customer has a separate Kion subscription.")
    has_music_subscription: bool = Field(default=False, description="Whether the customer has a separate Music subscription.")
    has_strings_subscription: bool = Field(default=False, description="Whether the customer has a separate Strings subscription.")
    has_mts_bank_debit_card: bool = Field(default=False, description="Whether the customer has an MTS Bank debit card.")
    has_mts_bank_credit_card: bool = Field(default=False, description="Whether the customer has an MTS Bank credit card.")
    has_mts_money_debit_card: bool = Field(default=False, description="Whether the customer has an MTS Money debit card.")
    has_mts_money_credit_card: bool = Field(default=False, description="Whether the customer has an MTS Money credit card.")
    has_mts_money_virtual_card: bool = Field(default=False, description="Whether the customer has an MTS Money virtual card.")

class CustomerCreateResponse(BaseModel):
    status: str = Field(..., description="Status of the customer creation operation.")
    phone_number: str = Field(..., description="Phone number of the created customer.")
    message: Optional[str] = Field(default=None, description="Additional message or error detail.")

class CustomerRetrieveResponse(BaseModel):
    status: str = Field(..., description="Status of the retrieval operation.")
    customer: Optional[Customer] = Field(default=None, description="Retrieved customer data.")
    message: Optional[str] = Field(default=None, description="Additional message or error detail.")

class HistoryEntry(BaseModel):
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number).")
    user_text: str = Field(default="", description="Text from the user.")
    operator_response: str = Field(default="", description="Response from the operator.")
    timestamp: str = Field(default="", description="Timestamp of the conversation turn.")
    role: str = Field(default="unknown", description="Role of the speaker (user/assistant/unknown).")

class UserMessageInput(BaseModel):
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number).")
    user_text: str = Field(..., description="The latest message from the user in Russian.")
    session_id: Optional[str] = Field(default=None, description="Legacy session ID for backward compatibility (temporary).")
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
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number).")
    session_id: Optional[str] = Field(default=None, description="Legacy session ID for backward compatibility (temporary).")
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
        default=None, description="Customer profile data for personalized processing."
    )
