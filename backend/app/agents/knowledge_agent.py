import json
from typing import List, Dict
from app.models.schemas import AgentResponse, KnowledgeResult
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger

async def find_knowledge(text: str) -> AgentResponse:
    """
    Find relevant knowledge from the vector database using vector similarity.
    """
    try:
        app_logger.info(f"Knowledge Agent: Searching for relevant info for query: {text[:50]}...")
        # Query the vector DB service to get the most similar predefined queries
        results = await vector_db_service.query_vector_db(text, top_k=1)
        
        if not results:
            app_logger.warning(f"No relevant knowledge found for query: {text}")
            return AgentResponse(
                agent_name="KnowledgeAgent",
                result={"knowledge": [], "message": "No relevant information found."},
                confidence=0.0,
                error="No matching knowledge base entries."
            )

        # Get the most relevant result (top-1)
        top_result = results[0]
        matched_query = top_result.get("query", "unknown")  # Retrieve query from payload
        relevance_score = top_result.get("score", 0.0)
        matched_text = top_result.get("text", "")  # Directly use the stored answer
        matched_sources = top_result.get("sources", "")  # Directly use the stored sources

        # If relevance score is too low, consider it not relevant
        if relevance_score < 0.7:  # Threshold can be adjusted based on testing
            app_logger.warning(f"Low relevance score ({relevance_score}) for query: {text}")
            return AgentResponse(
                agent_name="KnowledgeAgent",
                result={"knowledge": [], "message": "No relevant information found with sufficient confidence."},
                confidence=relevance_score,
                error="Relevance score below threshold."
            )

        # Prepare the response with the matched knowledge
        knowledge_result = KnowledgeResult(
            document_id=matched_query,
            content=matched_text,  # Use directly from Qdrant payload
            relevance_score=relevance_score
        )

        app_logger.info(f"Knowledge Agent: Found relevant answer for query: {text[:50]} with score {relevance_score}")
        return AgentResponse(
            agent_name="KnowledgeAgent",
            result={
                "knowledge": [knowledge_result.dict()],
                "sources": matched_sources  # Use directly from Qdrant payload
            },
            confidence=relevance_score
        )

    except Exception as e:
        app_logger.error(f"Knowledge Agent failed for query {text}: {str(e)}")
        return AgentResponse(
            agent_name="KnowledgeAgent",
            result={"knowledge": [], "message": "Error processing knowledge query."},
            confidence=0.0,
            error=str(e)
        )
