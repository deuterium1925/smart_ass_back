# Smart Assistant Backend API Reference

## Overview
The **Smart Assistant Backend API** is a multi-agent Large Language Model (LLM) system designed to assist contact center operators by processing customer queries in real-time. This API facilitates interaction with customer data and conversation history using `phone_number` (format: `89XXXXXXXXX`) as the unique identifier for customers and `timestamp` (ISO 8601 format, UTC) for individual conversation turns. The system optimizes operator workflows by providing personalized, context-aware suggestions and quality feedback, enhancing customer service efficiency and reducing response times.

## Key Features
- **Customer Management**: Create, retrieve, or delete customer profiles with detailed attributes for personalized support.
- **Message Storage**: Store incoming user messages, returning a `timestamp` to reference each conversation turn. Automated Quality Assurance (QA) and Summary Agents are triggered only after an operator response is submitted.
- **On-Demand Conversation Analysis**: Enable operators to trigger analysis by Intent, Emotion, Knowledge, and Action Suggestion Agents for specific conversation turns or recent history.
- **Operator Response with Automated Feedback**: Submit operator responses to update conversation history, triggering QA and Summary Agents for immediate feedback on response quality and conversation summaries.
- **Manual Agent Trigger**: Manually trigger QA and Summary Agents for a specific conversation turn if an operator response is delayed indefinitely.
- **Personalization**: Integrate customer data (e.g., tariff plans, subscriptions) into agent suggestions for tailored operator responses.

## Workflow Overview
1. **Profile Creation**: A customer profile must be created using `/api/v1/customers/create` before any message processing or history updates. The `phone_number` must adhere to the format `89XXXXXXXXX` (11 digits starting with 89).
2. **Message Storage**: Incoming user messages are stored via `/api/v1/process`, returning a unique `timestamp` for the conversation turn. Automated QA and Summary Agents are **not run immediately**, ensuring feedback is contextually relevant to operator input.
3. **On-Demand Analysis**: Operators can request detailed analysis on-demand via `/api/v1/analyze`, targeting specific conversation turns (using `timestamps`) or recent history (using `history_limit`). Dependent agents (e.g., Action Suggestion) automatically run prerequisite agents (e.g., Intent, Emotion) for complete analysis.
4. **Operator Response Submission**: Operator responses are submitted via `/api/v1/submit_operator_response`, triggering QA and Summary Agents to provide feedback and summaries based on the operator's input for the specified `timestamp`.
5. **Manual Trigger for Delays**: If an operator response is delayed indefinitely, QA and Summary Agents can be manually triggered via `/api/v1/trigger_automated_agents/{phone_number}/{timestamp}` to generate feedback without waiting for operator input.

## Frontend Integration Guidelines
- **Strict Phone Number Format Enforcement**: All endpoints require a `phone_number` in the format `89XXXXXXXXX` (11 digits starting with 89) as the unique customer identifier. Validation errors will return HTTP 400 responses if the format is incorrect. Frontend input validation must align with this requirement to prevent errors.
- **Timestamp Identifier**: The `/process` endpoint returns a `timestamp` (ISO 8601 format, UTC) for each stored message, which must be used in `/analyze`, `/submit_operator_response`, or `/trigger_automated_agents` calls to reference specific conversation turns. Ensure this `timestamp` is stored and managed correctly in the frontend for accurate conversation tracking.
- **Delayed Automated Results**: Automated results (QA, Summary) are provided **only after operator response submission** via `/submit_operator_response` or manual triggering via `/trigger_automated_agents`. Frontend UIs must display placeholders or loading states for these results until they are available, ensuring a smooth user experience.
- **Error Handling**: Error messages are descriptive and reference `phone_number` and `timestamp` for traceability. Status codes are used consistently (e.g., 400 for bad input like invalid phone number format, 404 for not found, 500 for server errors) to facilitate user-friendly error handling in the frontend. Display appropriate messages to operators or log errors for debugging.
- **Loading States and Triggers**: Implement placeholders or loading states for QA and Summary feedback after storing a message via `/process`. Update these states once results are available via `/submit_operator_response` or `/trigger_automated_agents`. For real-time updates in cases of delayed operator responses, consider polling or WebSocket integration to fetch automated results dynamically.
- **Conversation History Display**: Without `turn_id`, the frontend must display conversation history using `timestamp` or a simple sequential numbering scheme (provided as `sequence_number` in `HistoryEntry`). Ensure the backend response metadata (e.g., `conversation_history` from `/analyze`) is used to build a coherent chat view.
- **Edge Cases**: Handle edge cases like reassigned phone numbers or typos in input by validating user input before API calls. Warn operators of potential data inconsistencies (e.g., via UI prompts) if deletion or reassignment scenarios are detected.

## API Endpoints

### Customer Management
- **POST /api/v1/customers/create**
  - **Description**: Create or update a customer profile with a normalized phone number (`89XXXXXXXXX`).
  - **Request Body**: JSON object with `phone_number` (format: `89XXXXXXXXX`) and optional attributes (e.g., `is_mts_subscriber`, `tariff_plan`) for personalization.
  - **Response**: JSON with `status` (e.g., "success"), `phone_number`, and `message` (e.g., "Customer profile created or updated successfully.").
  - **Status Codes**: 
    - 200 (success)
    - 400 (validation error, e.g., incorrect phone number format)
    - 500 (server error)
  - **Frontend Note**: Ensure `phone_number` is validated in the frontend to match `89XXXXXXXXX` format before submission to avoid validation errors. Display success or error messages based on `status` and `message` fields to inform operators.

- **GET /api/v1/customers/retrieve/{phone_number}**
  - **Description**: Retrieve a customer profile by phone number.
  - **Path Parameter**: `phone_number` (format: `89XXXXXXXXX`).
  - **Response**: JSON with `status` (e.g., "success" or "not_found"), `customer` (object or null), and `message` (e.g., "Customer profile retrieved successfully.").
  - **Status Codes**: 
    - 200 (success or not found)
    - 400 (validation error, e.g., incorrect phone number format)
    - 500 (server error)
  - **Frontend Note**: Use this endpoint to verify profile existence before processing messages. If `status` is "not_found", prompt the operator to create a profile via `/api/v1/customers/create`. Validate `phone_number` format in the UI to prevent errors.

- **DELETE /api/v1/customers/delete/{phone_number}**
  - **Description**: Delete a customer profile and all associated conversation history to maintain data consistency.
  - **Path Parameter**: `phone_number` (format: `89XXXXXXXXX`).
  - **Response**: JSON with `status` (e.g., "success") and `message` (e.g., "Customer profile and associated history deleted.").
  - **Status Codes**: 
    - 200 (success)
    - 400 (validation error or not found)
    - 500 (server error)
  - **Frontend Note**: Use with caution as deletion is permanent and removes all history. Warn operators via a confirmation dialog before triggering deletion. Validate `phone_number` format to avoid errors and display success or error messages based on `message` field.

### Message Processing
- **POST /api/v1/process**
  - **Description**: Store a user message and return a `timestamp` for the conversation turn. QA and Summary Agents are delayed until an operator response is submitted.
  - **Request Body**: JSON with `phone_number` (format: `89XXXXXXXXX`) and `user_text` (the customer's message in Russian).
  - **Response**: JSON with `status` (e.g., "success"), `message` (e.g., "User message stored successfully."), `timestamp` (ISO 8601 format), and placeholder `automated_results` (for QA and Summary).
  - **Status Codes**: 
    - 200 (success)
    - 400 (validation error or no profile found)
    - 500 (server error)
  - **Frontend Note**: Store the returned `timestamp` to reference this message in subsequent calls. Display placeholders or loading states for QA and Summary results until they are available via `/submit_operator_response` or `/trigger_automated_agents`. Validate `phone_number` format and ensure a customer profile exists before submission.

- **POST /api/v1/analyze**
  - **Description**: Analyze conversation history for actionable insights from Intent, Emotion, Knowledge, and Action Suggestion Agents.
  - **Request Body**: JSON with `phone_number` (format: `89XXXXXXXXX`), optional `timestamps` (list of specific timestamps to analyze), and `history_limit` (default: 10, for recent history if timestamps not specified).
  - **Response**: JSON with detailed analysis results (`intent`, `emotion`, `knowledge`, `suggestions`), `conversation_history`, `customer_data`, `current_timestamp`, and `consolidated_output` (quick summary for reference).
  - **Status Codes**: 
    - 200 (success)
    - 400 (validation error or no profile found)
    - 500 (server error)
  - **Frontend Note**: Use to display insights to operators. Note that QA and Summary results are only available after operator response or manual trigger and will show placeholders in this response. Use `conversation_history` to populate chat views, ordering by `timestamp` or `sequence_number`.

- **POST /api/v1/submit_operator_response**
  - **Description**: Submit an operator response for a specific conversation turn, updating history and triggering QA and Summary Agents for feedback.
  - **Request Body**: JSON with `phone_number` (format: `89XXXXXXXXX`), `timestamp` (ISO 8601 format from `/process`), and `operator_response` (operator's text response).
  - **Response**: JSON with `status` (e.g., "success"), `message` (e.g., "Operator response updated and automated agents processed successfully."), and `automated_results` (QA and Summary feedback).
  - **Status Codes**: 
    - 200 (success)
    - 400 (validation error or no profile found)
    - 404 (conversation turn not found)
    - 500 (server error)
  - **Frontend Note**: Use the `timestamp` from `/process` to update the correct conversation turn. Update UI placeholders with QA and Summary results from `automated_results` once returned. Ensure `phone_number` format is validated to avoid errors.

- **POST /api/v1/trigger_automated_agents/{phone_number}/{timestamp}**
  - **Description**: Manually trigger QA and Summary Agents for a specific conversation turn if an operator response is delayed indefinitely.
  - **Path Parameters**: `phone_number` (format: `89XXXXXXXXX`), `timestamp` (ISO 8601 format from `/process`).
  - **Response**: JSON with `status` (e.g., "success"), `message` (e.g., "Automated agents triggered successfully."), and `automated_results` (QA and Summary feedback).
  - **Status Codes**: 
    - 200 (success)
    - 400 (validation error or no profile found)
    - 404 (conversation turn not found)
    - 500 (server error)
  - **Frontend Note**: Use as a fallback mechanism for delayed operator responses to ensure feedback is available. Update UI placeholders with results from `automated_results`. Validate `phone_number` format and ensure the `timestamp` exists before triggering to prevent errors.

### Health Check
- **GET /health**
  - **Description**: Verify the API's operational status.
  - **Response**: JSON with `status` field (e.g., "ok").
  - **Status Codes**: 200 (success).
  - **Frontend Note**: Use periodically or on application startup to confirm backend availability before enabling operator actions. Display an offline status or warning if the endpoint fails to respond.

## Additional Resources
- **Interactive Documentation**: Access detailed endpoint specifications, parameters, and response formats via the Swagger UI at `/docs` or Redoc at `/redoc` on the deployed API server. Use these tools to test API calls and explore request/response structures interactively.
- **Support**: For integration issues, API enhancements, or bug reports, contact the backend team with specific error messages referencing `phone_number` and `timestamp` for traceability. Include HTTP status codes and response `message` fields in support requests for faster resolution.

## Key Differences from Previous Version
- **Removal of `turn_id`**: The identifier `turn_id` has been completely replaced with `timestamp` across all endpoints and responses for simplified conversation tracking. Frontend systems must adapt to use `timestamp` or `sequence_number` for ordering and referencing conversation turns.
- **Delayed QA and Summary Agents**: Unlike the previous version where QA and Summary Agents ran immediately after message storage, they now trigger only after an operator response via `/submit_operator_response` or manually via `/trigger_automated_agents`. Frontend UIs must handle this delay with appropriate placeholders.
- **Enhanced Phone Number Validation**: Strict validation enforces the `89XXXXXXXXX` format for `phone_number` across all endpoints to prevent duplicates and ensure data consistency. Frontend input fields must enforce this format to avoid frequent 400 errors.
- **New Manual Trigger Endpoint**: The `/trigger_automated_agents/{phone_number}/{timestamp}` endpoint has been added as a fallback for delayed operator responses, allowing frontend systems to request QA and Summary feedback independently of operator input.

## Best Practices for Integration
- **Input Validation**: Always validate `phone_number` to match the `89XXXXXXXXX` format before API calls to minimize 400 errors. Implement regex checks (e.g., `^89\d{9}$`) in frontend forms.
- **State Management**: Maintain a local mapping of `phone_number` to conversation `timestamps` to enable quick reference in UI interactions. Update UI states dynamically when QA and Summary results are received.
- **Error Recovery**: Implement retry mechanisms for transient 500 errors with exponential backoff, but handle 400 and 404 errors by prompting operators to correct input or create missing profiles.
- **User Experience**: Design chat interfaces to display conversation history chronologically using `timestamp` or `sequence_number`. Highlight loading states for delayed feedback and notify operators when automated results are ready.

This document serves as a comprehensive guide for frontend integration with the updated Smart Assistant Backend API. Adhering to the specified formats, workflows, and best practices will ensure optimal performance and a seamless operator experience in contact center operations.