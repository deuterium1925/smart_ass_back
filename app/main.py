from fastapi import FastAPI
from app.api.routers import process as process_router
from app.core.config import get_settings
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger
from app.agents.knowledge_agent import KNOWLEDGE_BASE  # Import the knowledge base
from qdrant_client.http.models import PointStruct  # Import PointStruct
import asyncio

settings = get_settings()

app = FastAPI(
    title="Smart Assistant Backend API",
)

# Include API routers
app.include_router(process_router.router, prefix="/api/v1", tags=["Processing"])

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    app_logger.info("Starting up Smart Assistant Backend...")
    await vector_db_service.ensure_collection()
    
    # Check if the collection already has points to avoid duplicate indexing
    try:
        collection_info = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.collection_name
        )
        if collection_info.points_count > 0:
            app_logger.info(f"Collection {vector_db_service.collection_name} already has {collection_info.points_count} points, skipping indexing.")
        else:
            app_logger.info(f"Collection {vector_db_service.collection_name} is empty, starting knowledge base indexing...")
            successful_indices = 0
            failed_indices = 0
            for entry in KNOWLEDGE_BASE:
                query_text = entry["query"]
                point_id = vector_db_service.generate_point_id(query_text)
                retries = 0
                embedding = None
                while retries < settings.MAX_RETRIES and embedding is None:
                    embedding = await vector_db_service.get_embedding(query_text)
                    if embedding is None:
                        retries += 1
                        app_logger.warning(f"Retry {retries}/{settings.MAX_RETRIES} for embedding of query: {query_text[:30]}...")
                        await asyncio.sleep(2 ** retries)
                if embedding:
                    point = PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "query": query_text,
                            "text": entry["correct_answer"],
                            "sources": entry["correct_sources"]
                        }
                    )
                    await asyncio.to_thread(
                        vector_db_service.client.upsert,
                        collection_name=vector_db_service.collection_name,
                        points=[point]
                    )
                    app_logger.info(f"Indexed knowledge base entry: {query_text[:30]}... with ID {point_id}")
                    successful_indices += 1
                else:
                    app_logger.warning(f"Skipped indexing for query: {query_text[:30]}... due to failed embedding after {settings.MAX_RETRIES} retries")
                    failed_indices += 1
            app_logger.info(f"Indexing completed: {successful_indices} entries indexed, {failed_indices} entries skipped due to errors.")
    except Exception as e:
        app_logger.error(f"Failed to check or index knowledge base: {str(e)}")
    
    app_logger.info("Startup completed.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    app_logger.info("Shutting down Smart Assistant Backend...")
