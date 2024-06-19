ES_41_PRICE_CALCULATION_API_SUCCESS_RESPONSE = {
    "piMessageId": "XXXXX",
    "data": [
        {
            "type": "success",
            "id": "V4",
            "number": "233",
            "message": "SALES_HEADER_IN has been processed successfully",
            "messageV1": "VBAKKOM",
            "parameter": "SALES_HEADER_IN",
            "system": "PEDCLNT039",
        },
        {
            "type": "success",
            "id": "V4",
            "number": "233",
            "message": "SALES_ITEM_IN has been processed successfully",
            "messageV1": "VBAPKOM",
            "messageV2": "000010",
            "parameter": "SALES_ITEM_IN",
            "row": 1,
            "system": "PEDCLNT039",
        },
    ],
    "orderItemsOut": [
        {
            "itemNo": "000010",
            "material": "Z02GBS160D117575BB",
            "targetQuantity": 605.000,
            "salesUnit": "PC",
            "plant": "25AB",
            "itemCategory": "ZPS1",
            "priceDate": "30/10/2023",
            "netPricePerUnit": 11.8,
            "netValue": 7139,
            "currency": "THB",
            "priceStatus": "S",
        }
    ],
    "conditionsOut": [
        {
            "itemNo": "000010",
            "conditionStepNo": "010",
            "conditionCount": "01",
            "conditionType": "ZPP1",
            "conditionRate": 11.8,
            "currency": "THB",
            "conditionUnit": "PC",
            "conditionPerUnit": 1,
            "conditionPriceDate": "30/10/2023",
            "conditionBaseBalue": 6050,
            "conditionExchgRate": 1,
            "numconvert": 336,
            "denominato": 1000,
            "conditionValue": 7139,
        },
        {
            "itemNo": "000010",
            "conditionStepNo": 745,
            "conditionCount": "01",
            "conditionType": "MWST",
            "conditionRate": 7,
            "conditionPriceDate": "30/10/2023",
            "conditionBaseBalue": 7139,
            "conditionValue": 499.73,
        },
        {
            "itemNo": "000010",
            "conditionStepNo": 960,
            "conditionCount": "01",
            "conditionType": "VPRS",
            "currency": "THB",
            "conditionUnit": "KG",
            "conditionPerUnit": 1000,
            "conditionPriceDate": "30/10/2023",
            "conditionBaseBalue": 2032.8,
            "conditionExchgRate": 1,
            "numconvert": 1,
            "denominato": 1,
        },
    ],
    "orderHeaderOut": {
        "orderAmtBeforeVat": 7139,
        "orderAmtVat": 499.73,
        "orderAmtAfterVat": 7638.73,
        "currency": "THB",
    },
}
