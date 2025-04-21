import json
from typing import List, Dict
from app.models.schemas import AgentResponse, KnowledgeResult
from app.services.vector_db import vector_db_service
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger
from app.data.knowledge_base import KNOWLEDGE_BASE

async def find_knowledge(text: str) -> AgentResponse:
    """
    Retrieve relevant information from the vector database using similarity search based on a batch of user messages.
    Generates a natural language response with an LLM using broader context from concatenated messages.
    Optimizes output length for use by downstream agents like action_agent.
    Returns an AgentResponse with knowledge content and confidence score for operator support.
    Prioritizes relevant content over arbitrary truncation to avoid losing critical information.
    Falls back to static knowledge base if vector search fails.
    """
    settings = get_settings()
    try:
        app_logger.info(f"Knowledge Agent: Searching for relevant info for query: {text[:50]}...")
        # Query the vector DB service to get the top relevant documents
        results = await vector_db_service.query_vector_db(text, top_k=5)  # Increased to 5 for debugging
        
        if not results:
            app_logger.warning(f"No relevant knowledge found for query: {text}")
            # Fallback to static knowledge base search
            return fallback_to_static_knowledge(text)

        # Log retrieved documents for debugging
        app_logger.debug(f"Knowledge Agent: Retrieved {len(results)} documents for query: {text[:50]}")
        for i, result in enumerate(results):
            app_logger.debug(f"Document {i+1}: Query='{result.get('query', 'unknown')}', Score={result.get('score', 0.0)}")

        # Extract content and scores from top results with sufficient relevance
        knowledge_chunks = []
        sources = []
        avg_relevance_score = 0.0
        for result in results:
            relevance_score = result.get("score", 0.0)
            content = result.get("text", "")
            query = result.get("query", "unknown")
            source = result.get("sources", "")
            
            if relevance_score >= 0.7:
                knowledge_chunks.append(f"Документ: {query}\nСодержание: {content}")
                if source and source not in sources:
                    sources.append(source)
                avg_relevance_score += relevance_score
        
        if not knowledge_chunks:
            app_logger.warning(f"No documents met relevance threshold (0.7) for query: {text}")
            # Fallback to static knowledge base search
            return fallback_to_static_knowledge(text)

        avg_relevance_score /= len(knowledge_chunks)
        context = "\n\n".join(knowledge_chunks)
        # Increase truncation limit to retain more information, warn if truncated
        truncation_limit = 2000  # Increased from 800 to balance token limits and information retention
        truncation_occurred = False
        if len(context) > truncation_limit:
            context = context[:truncation_limit] + "... (сокращено для обработки, часть информации может быть утеряна)"
            truncation_occurred = True
            app_logger.warning(f"Knowledge Agent: Context truncated to {truncation_limit} characters for query: {text[:50]}")
        else:
            app_logger.debug(f"Knowledge Agent: Context length within limit ({len(context)} characters) for query: {text[:50]}")
        
        # Generate a concise response using LLM based on retrieved context, considering batch input
        prompt = f"""
        Вы - ассистент контакт-центра, помогающий оператору ответить на запрос клиента.
        Ваша задача - сформулировать точный, полезный и естественный ответ на основе предоставленной информации из базы знаний.
        Учитывайте, что запрос может представлять собой набор сообщений клиента, поэтому ответ должен учитывать общий контекст.
        Используйте только релевантные данные из контекста. Если информация недостаточна, укажите это.
        Ответ должен быть на русском языке, кратким (не более 200 слов) и ориентированным на помощь клиенту.
        Если контекст был сокращен, добавьте предупреждение, что информация может быть неполной.
        
        Запрос клиента (или набор сообщений): {text}
        Контекст из базы знаний:
        {context}
        
        Ответ для клиента:
        """
        
        app_logger.debug(f"Knowledge Agent: Generating response for query: {text[:50]} with context length: {len(context)}")
        generated_response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.KNOWLEDGE_MODEL,
            temperature=0.5  # Moderate temperature for balanced output
        )
        
        if not generated_response:
            app_logger.error(f"Knowledge Agent: Failed to generate response for query: {text[:50]}")
            # Fallback to raw content from top document if LLM fails
            fallback_content = results[0].get("text", "Информация по вашему запросу найдена, но сгенерировать ответ не удалось. Вот основное содержание из базы знаний.")
            if len(fallback_content) > 500:
                fallback_content = fallback_content[:500] + "..."
            app_logger.info(f"Knowledge Agent: Using fallback content for query: {text[:50]}")
            knowledge_result = KnowledgeResult(
                document_id="fallback_response",
                content=fallback_content,
                relevance_score=avg_relevance_score
            )
            return AgentResponse(
                agent_name="KnowledgeAgent",
                result={
                    "knowledge": [knowledge_result.dict()],
                    "sources": "; ".join(sources) if sources else "No sources available."
                },
                confidence=avg_relevance_score,
                error="LLM response generation failed, using fallback content."
            )

        # Increase truncation limit for generated response and warn if truncated
        if len(generated_response) > truncation_limit:
            generated_response = generated_response[:truncation_limit] + "... (сокращено, информация может быть неполной)"
            app_logger.warning(f"Knowledge Agent: Generated response truncated to {truncation_limit} characters for query: {text[:50]}")
            truncation_occurred = True
        else:
            app_logger.debug(f"Knowledge Agent: Generated response length within limit ({len(generated_response)} characters) for query: {text[:50]}")

        # Append a truncation warning to the response if truncation occurred at any stage
        if truncation_occurred:
            generated_response += "\n\nВнимание: Часть информации была сокращена из-за ограничений длины. Для полного ответа уточните детали запроса."

        knowledge_result = KnowledgeResult(
            document_id="generated_response",
            content=generated_response,
            relevance_score=avg_relevance_score
        )

        app_logger.info(f"Knowledge Agent: Generated response for query: {text[:50]} with avg score {avg_relevance_score}")
        return AgentResponse(
            agent_name="KnowledgeAgent",
            result={
                "knowledge": [knowledge_result.dict()],
                "sources": "; ".join(sources) if sources else "No sources available."
            },
            confidence=avg_relevance_score
        )

    except Exception as e:
        app_logger.error(f"Knowledge Agent failed for query {text}: {str(e)}")
        # Fallback to static knowledge base on exception
        return fallback_to_static_knowledge(text)

def fallback_to_static_knowledge(text: str) -> AgentResponse:
    """
    Fallback mechanism to search static KNOWLEDGE_BASE if vector search fails or returns no relevant results.
    Searches for partial matches in query field and returns the first matching entry.
    """
    app_logger.info(f"Knowledge Agent: Falling back to static knowledge base for query: {text[:50]}")
    text_lower = text.lower()
    for entry in KNOWLEDGE_BASE:
        query = entry.get("query", "").lower()
        if text_lower in query or any(word in query for word in text_lower.split()):
            app_logger.info(f"Knowledge Agent: Found matching static entry for query: {text[:50]} - {entry['query']}")
            knowledge_result = KnowledgeResult(
                document_id="static_fallback",
                content=entry.get("correct_answer", "No content available."),
                relevance_score=0.75  # Arbitrary confidence for fallback
            )
            return AgentResponse(
                agent_name="KnowledgeAgent",
                result={
                    "knowledge": [knowledge_result.dict()],
                    "sources": entry.get("correct_sources", "No sources available.")
                },
                confidence=0.75,
                error="Vector search failed, using static knowledge base fallback."
            )
    
    app_logger.warning(f"Knowledge Agent: No matching entry found in static knowledge base for query: {text[:50]}")
    return AgentResponse(
        agent_name="KnowledgeAgent",
        result={"knowledge": [], "message": "No relevant information found even in static fallback."},
        confidence=0.0,
        error="No matching knowledge base entries in vector or static search."
    )
