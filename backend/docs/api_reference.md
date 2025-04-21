# Smart Assistant Backend API Reference

## Overview
The Smart Assistant Backend API is a multi-agent LLM system designed to support contact center operators by processing customer queries in real-time. This API enables interaction with customer data and conversation history using `phone_number` (format: `89XXXXXXXXX`) as the unique identifier for customers and `timestamp` (ISO 8601 format) for individual conversation turns. The system is designed to optimize operator workflows with personalized, context-aware suggestions and quality feedback.

## Key Features
- **Customer Management**: Create, retrieve, or delete customer profiles with detailed attributes for personalized support.
- **Message Storage**: Store incoming user messages, returning a `timestamp` for reference. QA and Summary Agents are triggered only after operator response.
- **On-Demand Conversation Analysis**: Trigger analysis by Intent, Emotion, Knowledge, and Action Suggestion Agents for specific conversation turns or recent history.
- **Operator Response with Automated Feedback**: Submit operator responses, triggering QA and Summary Agents for immediate feedback on response quality and conversation summary.
- **Manual Agent Trigger**: Manually trigger QA and Summary Agents if an operator response is delayed indefinitely.
- **Personalization**: Integrate customer data (e.g., tariff plans, subscriptions) into agent suggestions for context-aware responses.

## Workflow Overview
1. **Profile Creation**: A customer profile must be created using `/api/v1/customers/create` before any message processing or history updates can occur. The `phone_number` must be in the format `89XXXXXXXXX` (11 digits starting with 89).
2. **Message Storage**: Incoming user messages are stored via `/api/v1/process`, returning a unique `timestamp` for the conversation turn. Automated QA and Summary Agents are **not run immediately** to ensure feedback is contextually relevant to operator input.
3. **On-Demand Analysis**: Operators can request detailed analysis on-demand via `/api/v1/analyze`, targeting specific conversation turns (via `timestamps`) or recent history (via `history_limit`). Dependent agents (e.g., Action Suggestion) automatically run prerequisite agents (e.g., Intent, Emotion) for complete analysis.
4. **Operator Response Submission**: Operator responses are submitted via `/api/v1/submit_operator_response`, triggering QA and Summary Agents to provide feedback and summaries based on the operator's input for the specified `timestamp`.
5. **Manual Trigger for Delays**: If an operator response is delayed, QA and Summary Agents can be manually triggered via `/api/v1/trigger_automated_agents/{phone_number}/{timestamp}` to generate feedback without waiting for operator input.

## Frontend Integration Guidelines
- **Phone Number Format**: All endpoints require a valid `phone_number` in the format `89XXXXXXXXX` (11 digits starting with 89) as the customer identifier to ensure data consistency and prevent duplicates. Validation errors will return HTTP 400 responses if the format is incorrect.
- **Timestamp Identifier**: The `/process` endpoint returns a `timestamp` (ISO 8601 format, UTC) for each stored message, which must be used in `/analyze`, `/submit_operator_response`, or `/trigger_automated_agents` calls to reference specific conversation turns.
- **Delayed Automated Results**: Automated results (QA, Summary) are provided **only after operator response submission** or manual triggering via `/trigger_automated_agents`. Frontend UIs must display placeholders or loading states for these results until they are available.
- **Error Handling**: Error messages are descriptive and reference `phone_number` and `timestamp` for traceability. Status codes are used consistently (e.g., 400 for bad input like invalid phone number format, 404 for not found, 500 for server errors) to facilitate user-friendly error handling.
- **Loading States and Triggers**: For seamless user experience, implement placeholders or loading states for QA and Summary feedback after storing a message via `/process`. Update these states once results are available via `/submit_operator_response` or `/trigger_automated_agents`. Consider polling or WebSocket integration if real-time updates are needed for delayed operator responses.

## API Endpoints

### Customer Management
- **POST /api/v1/customers/create**
  - **Description**: Create or update a customer profile with a normalized phone number (`89XXXXXXXXX`).
  - **Request Body**: JSON object with `phone_number` (format: `89XXXXXXXXX`) and optional attributes (e.g., `is_mts_subscriber`, `tariff_plan`).
  - **Response**: JSON with `status`, `phone_number`, and `message`.
  - **Status Codes**: 200 (success), 400 (validation error), 500 (server error).
  - **Frontend Note**: Ensure `phone_number` is in correct format before submission to avoid validation errors.

- **GET /api/v1/customers/retrieve/{phone_number}**
  - **Description**: Retrieve a customer profile by phone number.
  - **Path Parameter**: `phone_number` (format: `89XXXXXXXXX`).
  - **Response**: JSON with `status`, `customer` (object or null), and `message`.
  - **Status Codes**: 200 (success/not found), 400 (validation error), 500 (server error).
  - **Frontend Note**: Use to verify profile existence before processing messages.

- **DELETE /api/v1/customers/delete/{phone_number}**
  - **Description**: Delete a customer profile and all associated conversation history.
  - **Path Parameter**: `phone_number` (format: `89XXXXXXXXX`).
  - **Response**: JSON with `status` and `message`.
  - **Status Codes**: 200 (success), 400 (validation error/not found), 500 (server error).
  - **Frontend Note**: Use with caution as deletion is permanent and removes all history.

### Message Processing
- **POST /api/v1/process**
  - **Description**: Store a user message and return a `timestamp` for the turn. QA/Summary Agents are delayed until operator response.
  - **Request Body**: JSON with `phone_number` (format: `89XXXXXXXXX`) and `user_text`.
  - **Response**: JSON with `status`, `message`, `timestamp`, and placeholder `automated_results`.
  - **Status Codes**: 200 (success), 400 (validation error/no profile), 500 (server error).
  - **Frontend Note**: Display placeholders for QA/Summary results until operator response is submitted.

- **POST /api/v1/analyze**
  - **Description**: Analyze conversation history for actionable insights (Intent, Emotion, Knowledge, Suggestions).
  - **Request Body**: JSON with `phone_number` (format: `89XXXXXXXXX`), optional `timestamps`, and `history_limit` (default: 10).
  - **Response**: JSON with detailed analysis results and conversation history.
  - **Status Codes**: 200 (success), 400 (validation error/no profile), 500 (server error).
  - **Frontend Note**: Use to display insights; note QA/Summary are separate and delayed.

- **POST /api/v1/submit_operator_response**
  - **Description**: Submit operator response for a turn, triggering QA and Summary feedback.
  - **Request Body**: JSON with `phone_number` (format: `89XXXXXXXXX`), `timestamp`, and `operator_response`.
  - **Response**: JSON with `status`, `message`, and `automated_results` (QA/Summary feedback).
  - **Status Codes**: 200 (success), 400 (validation error/no profile), 500 (server error).
  - **Frontend Note**: Update UI with QA/Summary results once returned in response.

- **POST /api/v1/trigger_automated_agents/{phone_number}/{timestamp}**
  - **Description**: Manually trigger QA and Summary Agents if operator response is delayed.
  - **Path Parameters**: `phone_number` (format: `89XXXXXXXXX`), `timestamp` (ISO 8601 format).
  - **Response**: JSON with `status`, `message`, and `automated_results` (QA/Summary feedback).
  - **Status Codes**: 200 (success), 400 (validation error/no profile), 404 (turn not found), 500 (server error).
  - **Frontend Note**: Use as fallback for delayed operator responses to update UI with results.

### Health Check
- **GET /health**
  - **Description**: Check API operational status.
  - **Response**: JSON with `status` field (e.g., "ok").
  - **Status Codes**: 200 (success).
  - **Frontend Note**: Use to verify backend availability before operations.

## Additional Resources
- **Interactive Documentation**: Access detailed endpoint specifications, parameters, and response formats via the Swagger UI at `/docs` or Redoc at `/redoc` on the deployed API server.
- **Support**: For integration issues or API enhancements, contact the backend team with specific error messages referencing `phone_number` and `timestamp` for traceability.

This document serves as a comprehensive guide for frontend integration with the Smart Assistant Backend API. Ensure all interactions adhere to the specified formats and workflows for optimal performance and user experience.