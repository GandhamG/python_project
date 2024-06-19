ES_17 = {
    "piMessageId": "PIPXXXXXXXXXXXXXXXX",
    "salesdocument": "0411088207",
    "data": [
        {
            "type": "S",
            "id": "V1",
            "number": "311",
            "message": "Standard Order 411089146 has been saved",
            "logNo": "",
            "logMsgNo": "",
            "messageV1": "Standard Order",
            "messageV2": "0411089146",
            "messageV3": "",
            "messageV4": "",
            "parameter": "SALES_HEADER_IN",
            "row": 0,
            "field": "",
            "system": "PEPCLNT099",
        }
    ],
    "orderItemsOut": [
        {
            "itemNo": "000010",
            "materialNo": "Z02DBP400D31004300",
            "customerMaterial": "",
            "targetQuantity": 0,
            "salesUnit": "ROL",
            "plant": "7561",
            "shippingPoint": "7581",
            "route": "711006",
            "poNo": "",
            "poItemNo": "10",
            "itemCategory": "ZTAN",
            "prcGroup1": "K08",
            "prcGroup2": "",
            "poNo2": "",
            "poDateS": "03/06/2022",
            "poitemNoS": "",
            "overDeliveryTol": 5,
            "underDeliveryTol": 5,
            "paymentTerm": "",
            "netValue": 58.8,
            "currency": "THB",
            "prNo": "",
            "pritem": "",
            "rejectReason": "",
        }
    ],
    "orderSchedulesOut": [
        {
            "itemNo": "000010",
            "scheduleLine": "0001",
            "scheduleLinecate": "ZC",
            "requestDate": "13/06/2022",
            "requestQty": 5,
            "comfirmQty": 3,
            "DeliveryBlock": "",
        }
    ],
    "incompleteLogOut": [
        {
            "documentNo": "511176306",
            "itemNo": "000010",
            "scheduleLine": "0000",
            "partnerRole": "",
            "tableName": "VBKD",
            "fieldName": "BZIRK",
            "fieldText": "Sales district",
        }
    ],
    "creditStatusCode": "B",
    "creditStatusText": "Credit check was executed, document not OK",
}

ES_17_ERROR = {
    "piMessageId": "PIPXXXXXXXXXXXXXXXX",
    "salesdocument": "0411088207",
    "data": [
        {
            "type": "E",
            "id": "V1",
            "number": "311",
            "message": "Standard Order 411089146 has been saved",
            "logNo": "",
            "logMsgNo": "",
            "messageV1": "Standard Order",
            "messageV2": "0411089146",
            "messageV3": "",
            "messageV4": "",
            "parameter": "SALES_HEADER_IN",
            "row": 0,
            "field": "",
            "system": "PEPCLNT099",
        }
    ],
    "orderItemsOut": [
        {
            "itemNo": "000010",
            "materialNo": "Z02DBP400D31004300",
            "customerMaterial": "",
            "targetQuantity": 0,
            "salesUnit": "ROL",
            "plant": "7561",
            "shippingPoint": "7581",
            "route": "711006",
            "poNo": "",
            "poItemNo": "10",
            "itemCategory": "ZTAN",
            "prcGroup1": "K08",
            "prcGroup2": "",
            "poNo2": "",
            "poDateS": "03/06/2022",
            "poitemNoS": "",
            "overDeliveryTol": 5,
            "underDeliveryTol": 5,
            "paymentTerm": "",
            "netValue": 58.8,
            "currency": "THB",
            "prNo": "",
            "pritem": "",
            "rejectReason": "",
        }
    ],
    "orderSchedulesOut": [
        {
            "itemNo": "000010",
            "scheduleLine": "0001",
            "scheduleLinecate": "ZC",
            "requestDate": "13/06/2022",
            "requestQty": 5,
            "comfirmQty": 3,
            "DeliveryBlock": "",
        }
    ],
    "incompleteLogOut": [
        {
            "documentNo": "511176306",
            "itemNo": "000010",
            "scheduleLine": "0000",
            "partnerRole": "",
            "tableName": "VBKD",
            "fieldName": "BZIRK",
            "fieldText": "Sales district",
        }
    ],
    "creditStatusCode": "B",
    "creditStatusText": "Credit check was executed, document not OK",
}

data_sample = {
    "piMessageId": "PIPXXXXXXXXXXXXXXXX",
    "salesdocumentin": "0410273310",
    "testrun": "X",
    "orderHeaderIn": [
        {
            "reqDateH": "13/06/2022",
            "incoterms1": "CIF",
            "incoterms2": "จ.สมุทรปราการ2",
            "paymentTerms": "NT90",
            "poNo": "",
            "purchaseDate1": "",
            "priceGroup": "03",
            "priceDate": "13/06/2022",
            "currency": "THB",
            "customerGroup": "45",
            "salesDistrict": "075003",
            "shippingCondition": "01",
            "customerGroup1": "01",
            "customerGroup2": "",
            "customerGroup3": "",
            "customerGroup4": "",
            "customerGroup5": "",
            "deliveryBlock": "",
        }
    ],
    "orderHeaderInX": [
        {
            "requestDate": True,
            "incoterms1": True,
            "incoterms2": True,
            "paymentTerms": True,
            "poNo": True,
            "purchaseDate": True,
            "priceGroup": True,
            "priceDate": True,
            "currency": True,
            "customerGroup": True,
            "salesDistrict": True,
            "shippingCondition": True,
            "customerGroup1": True,
            "customerGroup2": True,
            "customerGroup3": True,
            "customerGroup4": True,
            "customerGroup5": True,
            "deliveryBlock": True,
        }
    ],
    "orderPartners": [
        {
            "partnerRole": "WE",
            "partnerNo": "0001002813",
            "itemNo": "000000",
            "addressLink": "12address",
        }
    ],
    "PartnerAddreses": [
        {
            "addressNo": "1",
            "name1": "นาย Customer Name1",
            "name2": "",
            "name3": "",
            "name4": "",
            "city": "",
            "zipCode": "10220",
            "district": "บางซื่อ",
            "street": "",
            "streetSuppl1": "",
            "streetSuppl2": "",
            "streetSuppl3": "",
            "location": "",
            "transportZone": "ZATH010029",
            "country": "TH",
            "telephoneNo": "",
        }
    ],
    "orderItemsIn": [
        {
            "itemNo": "000010",
            "targetQty": 5,
            "salesUnit": "ROL",
            "plant": "754F",
            "shippingPoint": "MY0067",
            "route": "7504",
            "orderNo": "MPS/PO/SKT023/21",
            "poItemNo": "000010",
            "itemCategory": "ZKS4",
            "priceGroup1": "",
            "priceGroup2": "",
            "poNo": "K00040064300100001WY0000000-1730896",
            "poitemNoS": "000010",
            "usage": "100",
            "overdlvtol": 0,
            "unlimitTol": "",
            "unddlvTol": 99,
            "reasonReject": "93",
            "paymentTerms": "TL60",
            "denominato": 1,
            "numconvert": 1000,
        }
    ],
    "orderItemsInx": [
        {
            "itemNo": "000010",
            "updateflag": "U",
            "targetQty": True,
            "salesUnit": True,
            "plant": True,
            "shippingPoint": True,
            "route": True,
            "purchaseOrderNo": True,
            "poItemNo": True,
            "itemCategory?:description": True,
            "priceGroup1": True,
            "priceGroup2": True,
            "poNo": True,
            "poDate": True,
            "poitemNoS": True,
            "overdlvtol": True,
            "unlimitTol": True,
            "unddlvTol": True,
            "reasonReject": True,
            "paymentTerms": True,
            "denominato": True,
            "numconvert": True,
        }
    ],
    "orderSchedulesIn": [
        {
            "itemNo": "000010",
            "scheduleLine": "0001",
            "scheduleLinecate": "ZC",
            "requestDate": "2022-06-07",
            "reqiestQuantity": 10,
            "confirmQuantity": 3,
            "deliveryBlock": "",
        }
    ],
    "orderSchedulesInx": [
        {
            "itemNo": "000010",
            "scheduleLine": "0001",
            "updateflag": True,
            "scheduleLineCate": True,
            "requestDate": True,
            "reqiestQuantity": True,
            "confirmQuantity": True,
            "deliveryBlock": True,
        }
    ],
    "orderConditionsIn": [
        {
            "itemNo": "000010",
            "conditionType": "ZPR2",
            "conditionValue": 4816,
            "currency": "THB",
            "conditionUnit": "ROL",
            "conditionPUnit": "1",
        }
    ],
    "orderConditionsInX": [
        {
            "ITM_NUMBER": "000010",
            "COND_TYPE": "ZPR2",
            "UPDATEFLAG": True,
            "COND_VALUE": True,
            "CURRENCY": True,
            "COND_UNIT": True,
            "COND_P_UNT": True,
        }
    ],
    "orderCfgsValues": [
        {"configId": "000010", "instId": "000010", "charc": "SDKUOM", "value": "MM"}
    ],
    "orderText": [
        {
            "itemNo": "000000",
            "textId": "Z016",
            "langu": "EN",
            "textLine": [{"textLine": "เพิ่มบอร์ดใหม่ส่วนลด 14%"}],
        }
    ],
}
