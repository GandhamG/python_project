CP_API_SUCCESS_RESPONSE = {
    "requestId": "1111111111",
    "sender": "e-ordering",
    "message": "Success",
    "orderHeader": {
        "tempOrder": "ORDER-0001",
        "updateDT": "2023-12-18T23:03:38.385343",
    },
    "orderItem": [
        {
            "itemNo": "000010",
            "matCode": "MAT001111111111111",
            "confirmDate": "18/12/2023",
            "plant": "253B",
        },
        {
            "itemNo": "000020",
            "matCode": "MAT001111111111112",
            "confirmDate": "18/12/2023",
            "plant": "253B",
        },
    ],
}

CP_API_SUCCESS_RESPONSE_BOM = {
    "requestId": "1328653389",
    "sender": "e-ordering",
    "message": "Success",
    "orderHeader": {"tempOrder": "4012367890", "updateDT": "2023-08-10T15:30:00Z"},
    "orderItem": [
        {
            "itemNo": "20",
            "matCode": "Z02CAF105D2090117N",
            "confirmDate": "20/09/2023",
            "plant": "7521",
            "matBom": "10Z03BOM_A",
        },
        {
            "itemNo": "30",
            "matCode": "Z02CAF105D2090117N",
            "confirmDate": "20/09/2023",
            "plant": "7521",
            "matBom": "10Z03BOM_A",
        },
    ],
}
CP_API_ERROR_RESPONSE = {
    "orderItem": [
        {},
        {
            "soldTo": ["Ensure this field has no more than 7 characters."],
            "shipTo": ["Ensure this field has no more than 7 characters."],
        },
    ]
}

CP_API_NON_BOM_SPLIT_SUCCESS_RESPONSE = {
    "requestId": "4985178665",
    "sender": "e-ordering",
    "message": "Success",
    "orderHeader": {
        "tempOrder": "0410278248",
        "updateDT": "2024-01-24T15:04:55.398962",
        "soNo": "0410278248",
    },
    "orderItem": [
        {
            "itemNo": "000010",
            "matCode": "Z02KP-275E1000127N",
            "confirmDate": "24/01/2024",
            "plant": "253B",
        },
        {
            "itemNo": "000030",
            "matCode": "Z02KP-275E1000127N",
            "confirmDate": "24/01/2024",
            "plant": "253B",
        },
    ],
}

CP_API_BOM_SPLIT_SUCCESS_RESPONSE = {
    "requestId": "1473463251",
    "sender": "e-ordering",
    "message": "Success",
    "orderHeader": {
        "tempOrder": "0410278248",
        "updateDT": "2024-01-24T19:52:39.161422",
        "soNo": "0410278248",
    },
    "orderItem": [
        {
            "itemNo": "000020",
            "matCode": "Z02KP-275E1000127N",
            "confirmDate": "24/01/2024",
            "plant": "253B",
            "matBom": "000010Z02KP-275E1000127N",
        },
        {
            "itemNo": "000040",
            "matCode": "Z02KP-275E1000127N",
            "confirmDate": "24/01/2024",
            "plant": "253B",
            "matBom": "000030Z02KP-275E1000127N",
        },
    ],
}
