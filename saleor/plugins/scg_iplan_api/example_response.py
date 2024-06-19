I_PLAN_RESPONSE_FAILURE = {
    "DDQResponse": {
        "requestId": "123456",
        "sender": "ABC123",
        "DDQResponseHeader": [
            {
                "headerCode": "AA112233",
                "DDQResponseLine": [
                    {
                        "lineNumber": "A01",
                        "productCode": "ProductCodeA01",
                        "status": "Confirmed",
                        "deliveryDate": "2022-09-20",
                        "dispatchDate": "2022-09-17",
                        "quantity": "4444",
                        "unit": "BU_SalesUnitA01",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA01",
                        "returnStatus": "Partial Success",
                        "returnCode": "Only X Tonnes available",
                        "returnCodeDescription": "ReturnCodeDescriptionA01",
                    },
                    {
                        "lineNumber": "A02",
                        "productCode": "AlternateProductCodeA02_001",
                        "status": "Confirmed",
                        "deliveryDate": "2022-10-20",
                        "dispatchDate": "2022-10-17",
                        "quantity": "4500",
                        "unit": "BU_SalesUnitA02",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA02",
                        "returnStatus": "Success",
                    },
                    {
                        "lineNumber": "A02_01",
                        "productCode": "AlternateProductCodeA02_001",
                        "status": "Confirmed",
                        "deliveryDate": "2022-10-20",
                        "dispatchDate": "2022-10-17",
                        "quantity": "3500",
                        "unit": "BU_SalesUnitA02_01",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA02",
                        "returnStatus": "Success",
                        "DDQResponseOperation": [
                            {
                                "operationNumber": "OperationNumberA02_01",
                                "operationType": "OperationTypeA02_01",
                                "workcentreCode": "WorkcentreCodeA02_01",
                                "reservationCode": "ReservationCodeA02_01",
                                "quantity": "3500",
                                "unit": "BU_SalesUnitA02_01",
                                "runEndDate": "2022-10-16",
                                "blockCode": "BlockCodeA02_01",
                                "runCode": "RunCodeA02_01",
                                "sfgProductCode": "optional_SfgProductCodeA02_01",
                            }
                        ],
                    },
                    {
                        "lineNumber": "A03",
                        "productCode": "ProductCodeA03",
                        "status": "Confirmed",
                        "deliveryDate": "2022-10-20",
                        "dispatchDate": "2022-10-17",
                        "quantity": "3800",
                        "unit": "BU_SalesUnitA03",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA03",
                        "returnStatus": "Success",
                    },
                    {
                        "lineNumber": "A03_01",
                        "productCode": "ProductCodeA03",
                        "status": "Confirmed",
                        "deliveryDate": "2022-10-24",
                        "dispatchDate": "2022-10-21",
                        "quantity": "4200",
                        "unit": "BU_SalesUnitA03_01",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA03",
                        "returnStatus": "Success",
                    },
                    {
                        "lineNumber": "A03_02",
                        "productCode": "ProductCodeA03",
                        "status": "Confirmed",
                        "deliveryDate": "2022-10-28",
                        "dispatchDate": "2022-10-25",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA03",
                        "returnStatus": "Success",
                        "DDQResponseOperation": [
                            {
                                "operationNumber": "OperationNumberA03_02",
                                "operationType": "OperationTypeA03_02",
                                "workcentreCode": "WorkcentreCodeA03_02",
                                "reservationCode": "ReservationCodeA03_02",
                                "quantity": "7000",
                                "unit": "BU_SalesUnitA03_02",
                                "runEndDate": "2022-10-16",
                                "blockCode": "BlockCodeA03_02",
                                "runCode": "RunCodeA03_02",
                            }
                        ],
                    },
                    {
                        "lineNumber": "A03_03",
                        "productCode": "ProductCodeA03",
                        "status": "Confirmed",
                        "deliveryDate": "2022-10-31",
                        "dispatchDate": "2022-10-28",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA03",
                        "returnStatus": "Success",
                        "DDQResponseOperation": [
                            {
                                "operationNumber": "OperationNumberA03_03",
                                "operationType": "OperationTypeA03_03",
                                "workcentreCode": "WorkcentreCodeA03_03",
                                "reservationCode": "ReservationCodeA03_03",
                                "quantity": "5000",
                                "unit": "BU_SalesUnitA03_03",
                                "runEndDate": "2022-10-16",
                                "blockCode": "BlockCodeA03_03",
                                "runCode": "RunCodeA03_03",
                            }
                        ],
                    },
                    {
                        "lineNumber": "A04",
                        "productCode": "ProductCodeA04",
                        "status": "Confirmed",
                        "deliveryDate": "NotLaterThanRequestDateA04",
                        "dispatchDate": "EqualOrBeforeDeliveryDateA04",
                        "onHandStock": True,
                        "warehouseCode": "WarehouseCodeA04",
                        "returnStatus": "Success",
                        "DDQResponseOperation": [
                            {
                                "operationNumber": "OperationNumberA04",
                                "operationType": "OperationTypeA04",
                                "workcentreCode": "WorkcentreCodeA04",
                                "reservationCode": "ReservationCodeA04",
                                "quantity": "12000",
                                "unit": "BU_SalesUnitA04",
                                "runEndDate": "NotLaterThanDeliveryDateA04",
                                "blockCode": "BlockCodeA04",
                                "runCode": "RunCodeA04",
                            }
                        ],
                    },
                    {
                        "lineNumber": "A05",
                        "productCode": "ProductCodeA05",
                        "status": "Confirmed",
                        "quantity": "0",
                        "unit": "BU_SalesUnitA05",
                        "onHandStock": True,
                        "returnStatus": "Success",
                        "returnCode": "No Inventory available",
                        "returnCodeDescription": "ReturnCodeDescriptionA05",
                    },
                ],
            }
        ],
    }
}

I_PLAN_RESPONSE_SUCCESS = {
    "DDQResponse": {
        "requestId": 123456,
        "sender": "ABC123",
        "DDQResponseHeader": [
            {
                "headerCode": "AA112233",
                "DDQResponseLine": [
                    {
                        "lineNumber": "A01",
                        "productCode": "productCodeA01",
                        "status": "Confirmed",
                        "deliveryDate": "2022-09-12T09:11:49.661Z",
                        "dispatchDate": "2022-09-12T09:11:49.661Z",
                        "quantity": 444,
                        "unit": "BU_SaleUnitA01",
                        "onHandStock": True,
                        "warehouseCode": "WareHouseCodeA01",
                        "returnStatus": "Partial Success",
                        "returnCode": "Only X Tonnes available",
                        "returnCodeDescription": "returnCodeDescriptionA01",
                        "DDQResponseOperation": [
                            {
                                "operationNumber": "operationNumberA02_01",
                                "operationType": "OperationTypeA02_01",
                                "workcentreCode": "WorkcentreCodeA02_01",
                                "reservationCode": "ReservationCodeA02_01",
                                "quantity": 3500,
                                "unit": "BU_SaleUnitA02_01",
                                "runEndDate": "2022-09-12T09:11:49.661Z",
                                "runCode": "RuncodeA02_01",
                                "sfgProductCode": "optional_SfgProductCodeA02_01",
                                "blockCode": "BlockCodeA02_01",
                            }
                        ],
                    },
                    {
                        "lineNumber": "A02",
                        "productCode": "productCodeA02",
                        "status": "Confirmed",
                        "deliveryDate": "2022-09-12T09:11:49.661Z",
                        "dispatchDate": "2022-09-12T09:11:49.661Z",
                        "quantity": 444,
                        "unit": "BU_SaleUnitA02",
                        "onHandStock": True,
                        "warehouseCode": "WareHouseCodeA02",
                        "returnStatus": "Success",
                        "returnCode": "Only X Tonnes available",
                        "returnCodeDescription": "returnCodeDescriptionA01",
                    },
                ],
            }
        ],
    }
}

I_PLAN_ACKNOWLEDGE_SUCCESS = {
    "DDQAcknowledge": {
        "requestId": "123456",
        "sender": "ABC123",
        "DDQAcknowledgeHeader": [
            {
                "headerCode": "AA112233",
                "DDQAcknowledgeLine": [
                    {"lineNumber": "BB01", "returnStatus": "Success"},
                    {"lineNumber": "BB02", "returnStatus": "Success"},
                    {"lineNumber": "BB03", "returnStatus": "Success"},
                    {"lineNumber": "BB04", "returnStatus": "Success"},
                    {"lineNumber": "BB05", "returnStatus": "Success"},
                    {"lineNumber": "BB06", "returnStatus": "Success"},
                    {"lineNumber": "BB07", "returnStatus": "Success"},
                    {"lineNumber": "BB08", "returnStatus": "Success"},
                    {"lineNumber": "BB09", "returnStatus": "Success"},
                ],
            }
        ],
    }
}


I_PLAN_ACKNOWLEDGE_FAILURE = {
    "DDQAcknowledge": {
        "requestId": "123456",
        "sender": "ABC123",
        "DDQAcknowledgeHeader": [
            {
                "headerCode": "AA112233",
                "DDQAcknowledgeLine": [
                    {"lineNumber": "BB01", "returnStatus": "Success"},
                    {"lineNumber": "BB02", "returnStatus": "Success"},
                    {"lineNumber": "BB03", "returnStatus": "Success"},
                    {"lineNumber": "BB04", "returnStatus": "Success"},
                    {"lineNumber": "BB05", "returnStatus": "Success"},
                    {"lineNumber": "BB06", "returnStatus": "Success"},
                    {"lineNumber": "BB07", "returnStatus": "Success"},
                    {"lineNumber": "BB08", "returnStatus": "Success"},
                    {"lineNumber": "BB09", "returnStatus": "Failure"},
                ],
            }
        ],
    }
}


I_PLAN_UPDATE_ORDER = {
    "OrderUpdateResponse": {
        "updateId": "uuid12344",
        "OrderUpdateResponseLine": [
            {
                "orderNumber": "0410273310",
                "lineCode": "000010",
                "returnStatus": "Success",
                "OrderSplitResponseLine": [
                    {
                        "newOrderNumber": "000020",
                        "newLineCode": "000020",
                        "returnStatus": "Success",
                    }
                ],
            }
        ],
    }
}

I_PLAN_65217_UPDATE_ORDER = {
    "OrderUpdateResponse": {
        "OrderUpdateResponseLine": [
            {
                "orderNumber": "orderNumber123",
                "lineCode": "10",
                "returnStatus": "FAILURE",
                "returnCode": "1",
                "returnCodeDescription": "4Unknown external reference order for orderNumber123",
            }
        ],
        "updateId": "1234",
    }
}

I_PLAN_65201_STOCK_ON_HAND = {
    "OnHandCSInquiryResponse": {
        "inquiryId": "123",
        "productCode": "54321",
        "returnStatus": "SUCCESS",
        "returnCode": "0",
        "returnCodeDescription": "This is a test response",
        "OnHandCSInquirySummaryResponse": {
            "customerOrdersQuantity": 1000.5,
            "dummyQuantity": 1000.5,
            "freeQuantity": 1000.5,
            "unit": "ROLL",
            "CustomerOrdersResponseLine": [
                {
                    "customerCode": "CUSTOMERCODE",
                    "orderNumber": "ORDERNUMBER",
                    "lineNumber": "LINENUMBER",
                    "deliveryDate": "2022-12-31",
                    "warehouseCode": "WAREHOUSECODE",
                    "reATPQuantity": 1000.5,
                    "pendingDeliveryQuantity": 1000.5,
                }
            ],
            "DummyListResponseLine": [
                {
                    "customerCode": "CUSTOMERCODE",
                    "warehouseCode": "WAREHOUSECODE",
                    "onHandQuantity": 1000.5,
                    "futureQuantity": 1000.5,
                }
            ],
            "FreeStockResponseLine": [
                {"warehouseCode": "WAREHOUSECODE", "onHandQuantity": 1000.5}
            ],
        },
    }
}
