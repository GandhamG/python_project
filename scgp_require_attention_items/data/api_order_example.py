ORDER_STATUS_EXAMPLE_REQUEST = {
    "OrderStatusRequest": {
        "updateId": "123456",
        "OrderStatusRequestLine": [
            {
                # triggered by ReATP process, Fully Assigned
                "orderNumber": "orderNumber123",
                "lineNumber": "lineNumber01",
                "statusDate": "statusDateYYYY-MM-DD",
                "quantity": "3500",
                "reATPQuantity": "3500",
                "unit": "unit_kg",
                "reATPStatus": "Fully Assigned",
                "forAttention": False,
            },
            {
                # triggered by ReATP process, Partially Assigned, Projected Inventory negative
                "orderNumber": "orderNumber321",
                "lineNumber": "lineNumber321_01",
                "statusDate": "statusDateYYYY-MM-DD",
                "quantity": "6000",
                "reATPQuantity": "4000",
                "unit": "unit_kg",
                "reATPStatus": "Partially Assigned",
                "forAttention": True,
            },
            # triggered by Run Production Operation, Allocated
            {
                "orderNumber": "orderNumber111",
                "lineNumber": "lineNumber111_01",
                "confirmedAvailabilityDate": "confirmedAvailabilityDateYYYY-MM-DD",
                "statusDate": "statusDateYYYY-MM-DD",
                "quantity": "4400",
                "operationStatus": "Allocated",
                "forAttention": False,
            },
            {
                # triggered by Trim Production Operation, Sent to Trim
                "orderNumber": "orderNumber222",
                "lineNumber": "lineNumber222_01",
                "statusDate": "statusDateYYYY-MM-DD",
                "quantity": "3500",
                "operationStatus": "Sent to Trim",
                "forAttention": False,
            },
            # triggered by Production Operation, Production in Progress
            {
                "orderNumber": "orderNumber222",
                "lineNumber": "lineNumber222_01",
                "statusDate": "statusDateYYYY-MM-DD",
                "quantity": "1200",
                "operationStatus": "Production in Progress",
            },
            # triggered by Production Operation, Production Completed
            {
                "orderNumber": "orderNumber222",
                "lineNumber": "lineNumber222_01",
                "statusDate": "statusDateYYYY-MM-DD",
                "quantity": "3500",
                "operationStatus": "Production Completed",
            },
        ],
    }
}

# only 1 example for Response as I-Plan will not act in any case (Success or Fail)
ORDER_STATUS_EXAMPLE_RESPONSE = {
    "OrderStatusResponse": {
        "updateId": "123456",
        "OrderStatusResponseLine": [
            {
                "orderNumber": "orderNumber123",
                "lineNumber": "lineNumber01",
                "returnStatus": "Success",
                "returnCode": "Code01",
                "returnDescription": "Error Description",
            }
        ],
    }
}
