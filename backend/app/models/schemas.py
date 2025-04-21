from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any

class Customer(BaseModel):
    """Represents a customer profile with attributes for personalized operator assistance in contact centers."""
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number in format 89XXXXXXXXX).")
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

    @validator('phone_number')
    def validate_and_normalize_phone_number(cls, v):
        """Validate and normalize phone number to format 89XXXXXXXXX."""
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) != 11 or not cleaned.startswith('89'):
            raise ValueError("Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX).")
        return cleaned

class CustomerCreateRequest(Customer):
    """Request model for creating or updating a customer profile in the vector database."""
    pass

class OperatorResponseInput(BaseModel):
    """Input model for submitting an operator's response to update conversation history."""
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number in format 89XXXXXXXXX).")
    operator_response: str = Field(..., description="The response from the operator for the current turn.")

    @validator('phone_number')
    def validate_and_normalize_phone_number(cls, v):
        """Validate and normalize phone number to format 89XXXXXXXXX."""
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) != 11 or not cleaned.startswith('89'):
            raise ValueError("Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX).")
        return cleaned

class CustomerCreateResponse(BaseModel):
    """Response model for customer profile creation or update operations."""
    status: str = Field(..., description="Status of the customer creation operation (e.g., 'success', 'error').")
    phone_number: str = Field(..., description="Phone number of the created customer (format: 89XXXXXXXXX).")
    message: Optional[str] = Field(default=None, description="Additional message or error detail.")

class CustomerRetrieveResponse(BaseModel):
    """Response model for retrieving a customer profile."""
    status: str = Field(..., description="Status of the retrieval operation (e.g., 'success', 'not_found').")
    customer: Optional[Customer] = Field(default=None, description="Retrieved customer data.")
    message: Optional[str] = Field(default=None, description="Additional message or error detail.")

class HistoryEntry(BaseModel):
    """Represents a single turn in a customer's conversation history for context in agent processing."""
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number in format 89XXXXXXXXX).")
    user_text: str = Field(default="", description="Text from the user for this conversation turn.")
    operator_response: str = Field(default="", description="Response from the operator for this conversation turn.")
    timestamp: str = Field(default="", description="Timestamp of the conversation turn in ISO 8601 format (UTC).")
    role: str = Field(default="unknown", description="Role of the speaker (user/assistant/unknown).")
    sequence_number: int = Field(default=0, description="Sequential number for ordering conversation history.")

class UserMessageInput(BaseModel):
    """Input model for processing a user's message in the contact center system."""
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number in format 89XXXXXXXXX).")
    user_text: str = Field(..., description="The latest message from the user in Russian.")
    operator_response: Optional[str] = Field(
        default="", description="Latest response from the operator, if available (not used in initial storage)."
    )

    @validator('phone_number')
    def validate_and_normalize_phone_number(cls, v):
        """Validate and normalize phone number to format 89XXXXXXXXX."""
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) != 11 or not cleaned.startswith('89'):
            raise ValueError("Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX).")
        return cleaned

class AnalysisRequest(BaseModel):
    """Input model for requesting on-demand conversation analysis."""
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number in format 89XXXXXXXXX).")
    timestamps: Optional[List[str]] = Field(
        default=None, description="List of specific timestamps (ISO 8601 format) to analyze. If not provided, analyzes recent history."
    )
    history_limit: Optional[int] = Field(
        default=10, description="Limit on the number of recent history turns to analyze if timestamps are not specified."
    )

    @validator('phone_number')
    def validate_and_normalize_phone_number(cls, v):
        """Validate and normalize phone number to format 89XXXXXXXXX."""
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) != 11 or not cleaned.startswith('89'):
            raise ValueError("Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX).")
        return cleaned

class AgentResponse(BaseModel):
    """Represents the output from an agent (e.g., Intent, Emotion) with results and confidence scores."""
    agent_name: str = Field(..., description="Name of the agent providing the response (e.g., IntentAgent).")
    result: Any = Field(..., description="Result or analysis data from the agent.")
    confidence: Optional[float] = Field(default=None, description="Confidence score for the result, if applicable.")
    error: Optional[str] = Field(default=None, description="Error message if processing failed.")

class Suggestion(BaseModel):
    """Represents a suggested action or response for the operator to use with a customer."""
    text: str = Field(..., description="Suggested action or response text for the operator in Russian.")
    type: str = Field(..., description="Type of suggestion (e.g., 'discount_offer', 'problem_resolution').")
    priority: Optional[int] = Field(default=1, description="Priority level of the suggestion (1-5, 1 being highest).")

class KnowledgeResult(BaseModel):
    """Represents a result from the knowledge base search with content and relevance score."""
    document_id: str = Field(..., description="Unique ID of the retrieved knowledge document.")
    content: str = Field(..., description="Relevant content snippet from the knowledge base.")
    relevance_score: float = Field(..., description="Relevance score for the document based on search similarity.")

class ProcessingResultOutput(BaseModel):
    """Output model consolidating results from all agents for operator assistance via /analyze endpoint."""
    phone_number: str = Field(..., description="Unique identifier for the customer (phone number in format 89XXXXXXXXX).")
    intent: Optional[AgentResponse] = Field(default=None, description="Intent detection result from IntentAgent.")
    emotion: Optional[AgentResponse] = Field(default=None, description="Emotion analysis result from EmotionAgent.")
    knowledge: Optional[AgentResponse] = Field(default=None, description="Knowledge retrieval result from KnowledgeAgent.")
    suggestions: List[Suggestion] = Field(default=[], description="List of actionable suggestions for the operator.")
    summary: Optional[AgentResponse] = Field(default=None, description="Summary of the conversation (available post-operator response).")
    qa_feedback: Optional[AgentResponse] = Field(default=None, description="Quality assurance feedback (available post-operator response).")
    consolidated_output: Optional[str] = Field(
        default=None, description="Consolidated summary of processing results for quick operator reference."
    )
    conversation_history: Optional[List[HistoryEntry]] = Field(
        default=None, description="Recent conversation history turns for the customer."
    )
    history_storage_status: Optional[bool] = Field(
        default=True, description="Status of storing the current conversation turn to history."
    )
    customer_data: Optional[Customer] = Field(
        default=None, description="Customer profile data for personalized processing."
    )
    current_timestamp: Optional[str] = Field(
        default=None, description="Timestamp for the most recent conversation turn in ISO 8601 format (UTC)."
    )

class ProcessMessageResponse(BaseModel):
    """Response model for storing a user message via /process endpoint."""
    status: str = Field(..., description="Status of the operation (e.g., 'success', 'error').")
    message: str = Field(..., description="Descriptive message about the operation result.")
    timestamp: str = Field(..., description="Timestamp of the stored conversation turn in ISO 8601 format (UTC).")
    automated_results: Dict[str, AgentResponse] = Field(
        ..., description="Placeholder results for Summary and QA agents (run after operator response)."
    )
