from fastapi import APIRouter, HTTPException, status, Body, Query
from app.models.schemas import CustomerCreateRequest, CustomerCreateResponse, CustomerRetrieveResponse, Customer
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger, log_customer_creation, log_customer_retrieval
import asyncio
from typing import List, Optional

router = APIRouter()

@router.post(
    "/create",
    response_model=CustomerCreateResponse,
    summary="Create or Update Customer Profile",
    description="""
    Creates or updates a customer profile using the phone number as a unique identifier. 
    Phone number must be in the format `89XXXXXXXXX` (11 digits starting with 89). 
    Supports detailed personalization with customer attributes for agent analysis.
    
    **Frontend Integration Notes**:
    - A customer profile must be created before using `/process`, `/analyze`, or `/submit_operator_response` endpoints.
    - Use `phone_number` as the primary key for all interactions with this API, ensuring format `89XXXXXXXXX` to avoid validation errors.
    - Check `status` and `message` for operation success or error details to display to users if necessary (e.g., validation failures or server errors).
    - Ensure all operations involving customer data reference this profile creation step to maintain data consistency.
    """,
    status_code=status.HTTP_200_OK,
)
async def create_customer(
    customer_data: CustomerCreateRequest = Body(...)
):
    """
    Endpoint to create or update a customer profile in the Qdrant customers collection.
    Updates existing profiles if the phone number matches, with checks for data consistency.
    Phone number is validated and normalized to format 89XXXXXXXXX.
    If a profile already exists, deletes old history to prevent data leakage for reassigned numbers.
    """
    try:
        # Check for existing customer profile
        existing_customer = await vector_db_service.retrieve_customer(customer_data.phone_number)
        operation_type = "Updating" if existing_customer else "Creating"
        app_logger.info(f"{operation_type} customer profile for {customer_data.phone_number}")

        # If customer exists, log differences for critical fields to detect potential conflicts
        if existing_customer:
            differences = []
            critical_fields = ["is_mts_subscriber", "tariff_plan", "has_mts_premium", "has_mobile", "has_home_internet", "has_home_tv"]
            for field in critical_fields:
                existing_value = getattr(existing_customer, field)
                new_value = getattr(customer_data, field)
                if existing_value != new_value:
                    differences.append(f"{field}: old={existing_value}, new={new_value}")
            if differences:
                app_logger.warning(f"Data consistency warning for {customer_data.phone_number}: Differences detected - {'; '.join(differences)}")
            else:
                app_logger.debug(f"No significant differences detected for existing customer {customer_data.phone_number}")
            # Delete old history to prevent data leakage for reassigned numbers
            app_logger.info(f"Deleting old history for {customer_data.phone_number} before updating profile to handle potential reassignment.")
            await vector_db_service.delete_customer_and_history(customer_data.phone_number)

        # Upsert customer data to Qdrant
        success = await vector_db_service.upsert_customer(customer_data)
        if not success:
            log_customer_creation(customer_data.phone_number, False, "Failed to store customer profile.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store customer profile for {customer_data.phone_number}."
            )
        log_customer_creation(customer_data.phone_number, True, "Customer profile created or updated successfully.")
        return CustomerCreateResponse(
            status="success",
            phone_number=customer_data.phone_number,
            message="Customer profile created or updated successfully."
        )
    except ValueError as ve:
        log_customer_creation(customer_data.phone_number if hasattr(customer_data, 'phone_number') else "invalid_input", False, f"Validation error: {str(ve)}")
        app_logger.error(f"Validation error for customer profile creation with phone number {customer_data.phone_number if hasattr(customer_data, 'phone_number') else 'invalid_input'}: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(ve)}",
        )
    except Exception as e:
        log_customer_creation(customer_data.phone_number if hasattr(customer_data, 'phone_number') else "unknown", False, f"Unexpected error: {str(e)}")
        app_logger.error(f"Error creating/updating customer profile for {customer_data.phone_number if hasattr(customer_data, 'phone_number') else 'unknown'}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@router.get(
    "/retrieve/{phone_number}",
    response_model=CustomerRetrieveResponse,
    summary="Retrieve Customer Profile",
    description="""
    Retrieves a customer profile using the provided phone number as the unique identifier in format `89XXXXXXXXX`. 
    Returns null if no profile exists.
    
    **Frontend Integration Notes**:
    - Use this endpoint to fetch customer data for display or before processing messages to ensure a profile exists.
    - Ensure `phone_number` is in format `89XXXXXXXXX` (11 digits starting with 89) before calling this endpoint to avoid validation errors.
    - Check `status` to determine if a customer was found (`success` or `not_found`) and handle accordingly in the UI (e.g., prompt for profile creation if not found).
    """,
    status_code=status.HTTP_200_OK,
)
async def retrieve_customer(phone_number: str):
    """
    Endpoint to fetch a customer profile from the Qdrant customers collection by phone number.
    Returns null if no profile exists. Validates phone number format before processing.
    """
    try:
        # Normalize and validate phone number using the same logic as Pydantic validator
        cleaned_phone = ''.join(filter(str.isdigit, phone_number))
        if len(cleaned_phone) != 11 or not cleaned_phone.startswith('89'):
            log_customer_retrieval(phone_number, False)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX)."
            )

        customer = await vector_db_service.retrieve_customer(cleaned_phone)
        log_customer_retrieval(cleaned_phone, bool(customer))
        if customer:
            return CustomerRetrieveResponse(
                status="success",
                customer=customer,
                message="Customer profile retrieved successfully."
            )
        else:
            return CustomerRetrieveResponse(
                status="not_found",
                customer=None,
                message=f"No customer found with phone number {cleaned_phone}."
            )
    except HTTPException as he:
        log_customer_retrieval(phone_number, False)
        app_logger.error(f"Validation error retrieving customer profile for {phone_number}: {he.detail}")
        raise
    except Exception as e:
        log_customer_retrieval(phone_number, False)
        app_logger.error(f"Error retrieving customer profile for {phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@router.delete(
    "/delete/{phone_number}",
    response_model=dict,
    summary="Delete Customer Profile and History",
    description="""
    Deletes a customer profile and all associated conversation history using the provided phone number as the unique identifier in format `89XXXXXXXXX`.
    Ensures no history remains without a customer profile.
    
    **Frontend Integration Notes**:
    - Use this endpoint to permanently delete a customer and their conversation history.
    - Ensure `phone_number` is in format `89XXXXXXXXX` (11 digits starting with 89) before calling this endpoint to avoid validation errors.
    - Check `status` and `message` for operation success or error details to display to users if necessary.
    - Warn users that deletion is permanent and cannot be undone, affecting all associated data.
    """,
    status_code=status.HTTP_200_OK,
)
async def delete_customer(phone_number: str):
    """
    Endpoint to delete a customer profile and all associated history from Qdrant.
    Enforces the relationship between customer and history by removing both.
    Validates phone number format before processing.
    """
    try:
        # Normalize and validate phone number
        cleaned_phone = ''.join(filter(str.isdigit, phone_number))
        if len(cleaned_phone) != 11 or not cleaned_phone.startswith('89'):
            app_logger.error(f"Invalid phone number format for deletion: {phone_number}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number must be 11 digits starting with '89' (format: 89XXXXXXXXX)."
            )

        app_logger.info(f"Deleting customer profile and history for {cleaned_phone}")
        success = await vector_db_service.delete_customer_and_history(cleaned_phone)
        if not success:
            app_logger.error(f"Failed to delete customer profile and history for {cleaned_phone}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No customer found with phone number {cleaned_phone} or deletion failed."
            )
        app_logger.info(f"Successfully deleted customer profile and history for {cleaned_phone}")
        return {"status": "success", "message": f"Customer profile and associated history deleted for {cleaned_phone}."}
    except HTTPException as he:
        app_logger.error(f"Error deleting customer profile for {phone_number}: {str(he.detail)}")
        raise
    except Exception as e:
        app_logger.error(f"Unexpected error deleting customer profile for {phone_number}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@router.get(
    "/list",
    response_model=dict,
    summary="List All Customers with Optional History",
    description="""
    Retrieves a paginated list of all customers with an option to include their conversation histories.
    Use pagination parameters to manage large datasets. Requires careful handling due to potential performance impact.
    
    **Frontend Integration Notes**:
    - Use this endpoint at app startup or for administrative views to list all customers.
    - Adjust `limit` and `offset` for pagination to handle large datasets efficiently.
    - Set `include_history=true` to load conversation histories, but note this may impact performance.
    - Check `total_count` to implement pagination controls in the UI.
    """,
    status_code=status.HTTP_200_OK,
)
async def list_customers(
    limit: int = Query(50, ge=1, le=500, description="Number of customers to retrieve per page"),
    offset: Optional[str] = Query(None, description="Offset ID for pagination, retrieved from previous response"),
    include_history: bool = Query(False, description="Whether to include conversation history for each customer")
):
    """
    Endpoint to fetch a paginated list of all customers from the Qdrant customers collection.
    Optionally includes conversation history for each customer if include_history is true.
    Uses scroll API for pagination to handle large datasets.
    """
    try:
        app_logger.info(f"Listing customers with limit={limit}, offset={offset}, include_history={include_history}")
        # Use Qdrant scroll API to paginate through customers
        search_result = await asyncio.to_thread(
            vector_db_service.client.scroll,
            collection_name=vector_db_service.customers_collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        customers_data = search_result[0]  # List of points (customer records)
        next_offset = search_result[1]  # Next offset for pagination
        
        customers = []
        total_count = (await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.customers_collection_name
        )).points_count
        
        for point in customers_data:
            customer_payload = point.payload
            try:
                customer_obj = Customer(**customer_payload)
                customer_entry = {"customer": customer_obj}
                if include_history:
                    history = await vector_db_service.retrieve_conversation_history(
                        phone_number=customer_payload.get("phone_number", ""),
                        limit=50  # Limit history per customer to avoid overload
                    )
                    customer_entry["history"] = history
                customers.append(customer_entry)
            except ValueError as ve:
                app_logger.warning(f"Skipping customer with invalid data: {customer_payload.get('phone_number', 'unknown')} - {str(ve)}")
                continue
        
        app_logger.info(f"Retrieved {len(customers)} customers out of {total_count} total (offset: {offset or 'start'})")
        return {
            "status": "success",
            "message": f"Retrieved {len(customers)} customers.",
            "customers": customers,
            "total_count": total_count,
            "next_offset": next_offset if next_offset else None,
            "limit": limit
        }
    except Exception as e:
        app_logger.error(f"Error listing customers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while listing customers: {str(e)}",
        )
