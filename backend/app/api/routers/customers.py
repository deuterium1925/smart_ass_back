from fastapi import APIRouter, HTTPException, status, Body
from app.models.schemas import CustomerCreateRequest, CustomerCreateResponse, CustomerRetrieveResponse
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger, log_customer_creation, log_customer_retrieval

router = APIRouter()

@router.post(
    "/create",
    response_model=CustomerCreateResponse,
    summary="Create or Update Customer Profile",
    description="Creates or updates a customer profile using the phone number as a unique identifier. Supports detailed personalization with customer attributes.",
    status_code=status.HTTP_200_OK,
)
async def create_customer(
    customer_data: CustomerCreateRequest = Body(...)
):
    """
    Endpoint to create or update a customer profile in the Qdrant customers collection.
    Updates existing profiles if the phone number matches, with checks for data consistency.
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
    except Exception as e:
        log_customer_creation(customer_data.phone_number, False, f"Unexpected error: {str(e)}")
        app_logger.error(f"Error creating/updating customer profile for {customer_data.phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@router.get(
    "/retrieve/{phone_number}",
    response_model=CustomerRetrieveResponse,
    summary="Retrieve Customer Profile",
    description="Retrieves a customer profile using the provided phone number as the unique identifier.",
    status_code=status.HTTP_200_OK,
)
async def retrieve_customer(phone_number: str):
    """
    Endpoint to fetch a customer profile from the Qdrant customers collection by phone number.
    Returns null if no profile exists.
    """
    try:
        customer = await vector_db_service.retrieve_customer(phone_number)
        log_customer_retrieval(phone_number, bool(customer))
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
                message=f"No customer found with phone number {phone_number}."
            )
    except Exception as e:
        log_customer_retrieval(phone_number, False)
        app_logger.error(f"Error retrieving customer profile for {phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )
