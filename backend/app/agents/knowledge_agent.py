import json
from typing import List, Dict
from app.models.schemas import AgentResponse, KnowledgeResult
from app.services.vector_db import vector_db_service
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.utils.logger import app_logger

async def find_knowledge(text: str) -> AgentResponse:
    """
    Find relevant knowledge from the vector database using vector similarity,
    then generate a natural language response using an LLM based on retrieved content.
    """
    settings = get_settings()
    try:
        app_logger.info(f"Knowledge Agent: Searching for relevant info for query: {text[:50]}...")
        # Query the vector DB service to get the top relevant documents
        results = await vector_db_service.query_vector_db(text, top_k=5)  # Increased to 5 for debugging
        
        if not results:
            app_logger.warning(f"No relevant knowledge found for query: {text}")
            return AgentResponse(
                agent_name="KnowledgeAgent",
                result={"knowledge": [], "message": "No relevant information found."},
                confidence=0.0,
                error="No matching knowledge base entries."
            )

        # Log all retrieved results for debugging
        app_logger.debug(f"Knowledge Agent: Retrieved {len(results)} documents for query: {text[:50]}")
        for i, result in enumerate(results):
            app_logger.debug(f"Document {i+1}: Query='{result.get('query', 'unknown')}', Score={result.get('score', 0.0)}")

        # Extract relevant content and scores from the top results
        knowledge_chunks = []
        sources = []
        avg_relevance_score = 0.0
        for result in results:
            relevance_score = result.get("score", 0.0)
            content = result.get("text", "")
            query = result.get("query", "unknown")
            source = result.get("sources", "")
            
            if relevance_score >= 0.5:  # Lowered threshold for debugging
                knowledge_chunks.append(f"Документ: {query}\nСодержание: {content}")
                if source and source not in sources:
                    sources.append(source)
                avg_relevance_score += relevance_score
        
        if not knowledge_chunks:
            app_logger.warning(f"No documents met relevance threshold (0.5) for query: {text}")
            return AgentResponse(
                agent_name="KnowledgeAgent",
                result={"knowledge": [], "message": "No relevant information found with sufficient confidence."},
                confidence=0.0,
                error="Relevance score below threshold."
            )

        avg_relevance_score /= len(knowledge_chunks)
        context = "\n\n".join(knowledge_chunks)
        # Truncate context to prevent LLM overload
        if len(context) > 2000:
            context = context[:2000] + "... (сокращено для обработки)"
            app_logger.debug(f"Knowledge Agent: Context truncated to 2000 characters for query: {text[:50]}")
        
        # Generate a response using LLM based on retrieved context
        prompt = f"""
        Вы - ассистент контакт-центра, помогающий оператору ответить на запрос клиента.
        Ваша задача - сформулировать точный, полезный и естественный ответ на основе предоставленной информации из базы знаний.
        Используйте только релевантные данные из контекста. Если информация недостаточна, укажите это.
        Ответ должен быть на русском языке, кратким и ориентированным на помощь клиенту.
        
        Запрос клиента: {text}
        Контекст из базы знаний:
        {context}
        
        Ответ для клиента:
        """
        
        app_logger.debug(f"Knowledge Agent: Generating response for query: {text[:50]} with context length: {len(context)}")
        generated_response = await llm_service.call_llm(
            prompt=prompt,
            model_name=settings.KNOWLEDGE_MODEL,
            temperature=0.5  # Moderate temperature for balanced creativity and accuracy
        )
        
        if not generated_response:
            app_logger.error(f"Knowledge Agent: Failed to generate response for query: {text[:50]}")
            # Fallback to raw content from the top document if LLM fails
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

        # Prepare the response with the generated content
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
        return AgentResponse(
            agent_name="KnowledgeAgent",
            result={"knowledge": [], "message": "Error processing knowledge query."},
            confidence=0.0,
            error=str(e)
        )