from datetime import datetime

data_example = [{
    "dp_no": "3312323121",
    "po_no": "123128678321",
    "so_no": "3123123123",
    "item_no": "30",
    "material_description": "CA 105M-88 DIA125N",
    "quantity": "20",
    "ship_to": "nguyenking",
    "gi_date": datetime.strptime("2022-12-11", "%Y-%m-%d"),
    "car_registration_no": "283123",
    "departure_place_positions": "cho ha long",
    "estimate_date_time": datetime.strptime("2022-10-31", "%Y-%m-%d"),
    "transport_status": "transported",
    "current_position": "halong",
    "remaining_distance_as_kilometer": "300",
    "estimated_arrival_datetime": datetime.strptime("2022-12-10", "%Y-%m-%d"),
    "sale_unit": "ม้วน",
    "gps_tracking":
            {
                "car_registration_no": "283123",
                "current_position": "cot dong ho",
                "carrier": "213321",
                "velocity": 50,
                "last_signal_received_datetime": datetime.strptime("2022-11-10 10:30", "%Y-%m-%d %H:%M"),
                "payment_number": "1263",
                "delivery_place": "ha noi",
                "car_status": "running",
                "destination_reach_time": datetime.strptime("12:00", "%H:%M").time(),
                "estimated_to_customer_from_current_location": datetime.strptime("14:00", "%H:%M").time(),
                "remaining_distance_as_kilometer": "80",
                "estimate_arrival_time": datetime.strptime("14:00", "%H:%M").time(),
                "distance_from_factory_to_customer": 200,
                "isssuance_of_invoice_date": datetime.strptime("2022-12-22", "%Y-%m-%d"),
                "delivery_deadline": datetime.strptime("2022-12-29", "%Y-%m-%d"),
                "shipment_no": "0410123850",
                "estimated_time": "3"
            }
},
    {
        "dp_no": "323121",
        "po_no": "12312321",
        "so_no": "3123123",
        "item_no": "10",
        "material_description": "กระดาษ KK175 Size2050mm. Dia127cm.",
        "quantity": "20",
        "ship_to": "nguyenking",
        "gi_date": datetime.strptime("2022-12-20", "%Y-%m-%d"),
        "car_registration_no": "232123",
        "departure_place_positions": "cho long bien",
        "estimate_date_time": datetime.strptime("2022-10-31", "%Y-%m-%d"),
        "transport_status": "partial delivery",
        "current_position": "halong",
        "remaining_distance_as_kilometer": "300",
        "estimated_arrival_datetime": datetime.strptime("2022-12-10", "%Y-%m-%d"),
        "sale_unit": "ม้วน",
        "gps_tracking":
            {
                "car_registration_no": "283123",
                "current_position": "cot dong ho",
                "carrier": "213321",
                "velocity": 50,
                "last_signal_received_datetime": datetime.strptime("2022-11-10 10:30", "%Y-%m-%d %H:%M"),
                "payment_number": "1263",
                "delivery_place": "ha noi",
                "car_status": "running",
                "destination_reach_time": datetime.strptime("12:00", "%H:%M").time(),
                "estimated_to_customer_from_current_location": datetime.strptime("14:00", "%H:%M").time(),
                "remaining_distance_as_kilometer": "80",
                "estimate_arrival_time": datetime.strptime("14:00", "%H:%M").time(),
                "distance_from_factory_to_customer": 200,
                "isssuance_of_invoice_date": datetime.strptime("2022-11-15", "%Y-%m-%d"),
                "delivery_deadline": datetime.strptime("2022-12-29", "%Y-%m-%d"),
                "shipment_no": "0410123850",
                "estimated_time": "3"
            }
    },
    {
        "dp_no": "3213275673121",
        "po_no": "1231323296781",
        "so_no": "3125463123",
        "item_no": "20",
        "material_description": "CA- 105T-79 DIA127 N",
        "quantity": "20",
        "ship_to": "hang dau",
        "gi_date": datetime.strptime("2022-12-24", "%Y-%m-%d"),
        "car_registration_no": "283123",
        "departure_place_positions": "cho ben thanh",
        "estimate_date_time": datetime.strptime("2022-10-31", "%Y-%m-%d"),
        "transport_status": "transported",
        "current_position": "halong",
        "remaining_distance_as_kilometer": "300",
        "estimated_arrival_datetime": datetime.strptime("2022-12-10", "%Y-%m-%d"),
        "sale_unit": "ม้วน",
        "gps_tracking":
            {
                "car_registration_no": "283123",
                "current_position": "cot dong ho",
                "carrier": "213321",
                "velocity": 50,
                "last_signal_received_datetime": datetime.strptime("2022-11-10 10:30", "%Y-%m-%d %H:%M"),
                "payment_number": "1263",
                "delivery_place": "ha noi",
                "car_status": "running",
                "destination_reach_time": datetime.strptime("12:00", "%H:%M").time(),
                "estimated_to_customer_from_current_location": datetime.strptime("14:00", "%H:%M").time(),
                "remaining_distance_as_kilometer": "80",
                "estimate_arrival_time": datetime.strptime("14:00", "%H:%M").time(),
                "distance_from_factory_to_customer": 200,
                "isssuance_of_invoice_date": datetime.strptime("2022-12-31", "%Y-%m-%d"),
                "delivery_deadline": datetime.strptime("2022-12-29", "%Y-%m-%d"),
                "shipment_no": "0410123850",
                "estimated_time": "3"
            }
    }

]


def resolve_customer_lms_report(input_data, info):
    return data_example
