import random
import uuid

import pytest
from django.utils import timezone
from faker import Faker

from saleor.account.models import User
from sap_master_data.models import MaterialMaster, SoldToMaster, SoldToMaterialMaster
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import (
    Contract,
    MaterialVariantMaster,
    Order,
    OrderLineIPlan,
    OrderLines,
)
from scg_checkout.graphql.helper import PAYMENT_TERM_MAPPING
from scg_checkout.models import ScgpMaterialGroup


@pytest.fixture
def user_for_sap_migrations(db):
    faker = Faker()
    users = []
    for _ in range(3):
        users.append(
            User(
                email=faker.email(),
                first_name=faker.first_name(),
                last_name=faker.last_name(),
            )
        )
    return User.objects.bulk_create(users)


@pytest.fixture
def sap_migration_sold_to_master(db):
    """Return sap_master_data.models.SoldToMaterialMaster objects"""
    faker = Faker()
    sold_to_list = []
    for _ in range(3):
        sold_to = SoldToMaster(
            sold_to_code=faker.numerify("#" * 10),
            sold_to_name=faker.name(),
        )
        sold_to_list.append(sold_to)

    sold_to_list = SoldToMaster.objects.bulk_create(sold_to_list)
    return sold_to_list


@pytest.fixture
def sap_migration_sold_to_material_master(db):
    """Return sap_master_data.models.SoldToMaterialMaster objects"""
    faker = Faker()
    sold_to = []
    for _ in range(3):
        sold_to.append(
            SoldToMaterialMaster(
                sold_to_code=faker.numerify("##########"),
                sales_organization_code=faker.numerify("####"),
                distribution_channel_code=faker.numerify("##"),
                sold_to_material_code=faker.bothify("??###-####"),
                material_code=faker.bothify("?????-#######"),
            )
        )
    return SoldToMaterialMaster.objects.bulk_create(sold_to)


@pytest.fixture
def sap_migration_contract(db, sap_migration_sold_to_master):
    """Return sap_migration.models.Contract objects"""
    faker = Faker()
    contract = []
    for _ in range(3):
        payment_term_key = random.choice(tuple(PAYMENT_TERM_MAPPING.keys()))
        contract.append(
            Contract(
                code=faker.numerify("#" * 10),
                po_no=str(uuid.uuid4()),
                sold_to_code=faker.numerify("#" * 10),
                sold_to=random.choice(sap_migration_sold_to_master),
                project_name=faker.bs(),
                payment_term_key=payment_term_key,
                payment_term=PAYMENT_TERM_MAPPING.get(
                    payment_term_key, "test payment term"
                ),
            )
        )
    return Contract.objects.bulk_create(contract)


@pytest.fixture
def sap_migration_order(db, sap_migration_contract):
    """Return sap_migration.models.Order objects"""
    faker = Faker()
    order = []
    for _ in range(3):
        contract = random.choice(sap_migration_contract)
        order.append(
            Order(
                po_no=contract.po_no,
                po_number=contract.po_no,
                saved_sap_at=timezone.now(),
                item_note=faker.bs(),
                type="customer",
                so_no=faker.numerify("#" * 10),
                contract=contract,
                ship_to=faker.numerify("#" * 10) + " - " + faker.address(),
            )
        )
    return Order.objects.bulk_create(order)


@pytest.fixture
def material_variant_mockup(db):
    # Create a mockup ScgpMaterialGroup object
    material_group = ScgpMaterialGroup.objects.create(name="Test Group", code="TG")

    # Create a mockup MaterialMaster object
    material_master = MaterialMaster.objects.create(
        material_code="MM001",
        description_th="Test Material (TH)",
        description_en="Test Material (EN)",
        material_group="Test Group",
        material_type="MT001",
        material_type_desc="Test Material Type",
        base_unit="BU001",
        base_unit_desc="Test Base Unit",
        delete_flag="N",
        net_weight=1.0,
        gross_weight=1.2,
        weight_unit="WU001",
        name="Test Material",
        sales_unit="SU001",
        scgp_material_group=material_group,
    )

    # Create a mockup MaterialVariantMaster object
    material_variant = MaterialVariantMaster.objects.create(
        material=material_master,
        name="Test Variant",
        code="MV001",
        weight=1.0,
        description_th="Test Variant (TH)",
        description_en="Test Variant (EN)",
        type="VT001",
        sales_unit="SU001",
        status="ST001",
        determine_type="DT001",
        key_combination="KC001",
        valid_from=timezone.now().date(),
        valid_to=(timezone.now() + timezone.timedelta(days=10)).date(),
        propose_reason="Test Reason",
        grade="A",
        basis_weight="100",
        diameter="10",
        variant_type="VT001",
    )

    return material_variant


@pytest.fixture
def sap_migration_order_line(sap_migration_order, material_variant_mockup):
    """Return sap_migration_order_line objects"""
    order = random.choice(sap_migration_order)
    order_lines = []

    material = material_variant_mockup.material

    i_plans = OrderLineIPlan.objects.create(
        attention_type=None,
        atp_ctp=None,
        atp_ctp_detail=None,
        block=None,
        run=None,
        iplant_confirm_quantity=None,
        item_status=None,
        original_date=None,
        inquiry_method_code=None,
        transportation_method=None,
        type_of_delivery=None,
        fix_source_assignment=None,
        split_order_item=None,
        partial_delivery=None,
        consignment=None,
        paper_machine=None,
    )

    quantity = 1
    line = OrderLines(
        order=order,
        item_no="000010",
        po_no="test_po_no_01",
        material=material,
        material_variant=material_variant_mockup,
        quantity=1,
        request_date=timezone.now().date(),
        sales_unit=material_variant_mockup.sales_unit,
        remark="remark test",
        iplan=i_plans,
        ship_to="ship to test value",
        type=OrderType.DOMESTIC.value,
        weight=material.gross_weight,
        weight_unit=material.weight_unit,
        total_weight=material.gross_weight * quantity,
        inquiry_method=InquiryMethodType.DOMESTIC.value,
    )
    order_lines.append(line)

    i_plans = OrderLineIPlan.objects.create(
        attention_type=None,
        atp_ctp=None,
        atp_ctp_detail=None,
        block=None,
        run=None,
        iplant_confirm_quantity=None,
        item_status=None,
        original_date=None,
        inquiry_method_code=None,
        transportation_method=None,
        type_of_delivery=None,
        fix_source_assignment=None,
        split_order_item=None,
        partial_delivery=None,
        consignment=None,
        paper_machine=None,
    )

    quantity = 1
    line = OrderLines(
        order=order,
        item_no="000020",
        po_no="test_po_no_01",
        material=material,
        material_variant=material_variant_mockup,
        quantity=1,
        request_date=timezone.now().date(),
        sales_unit=material_variant_mockup.sales_unit,
        remark="remark test",
        iplan=i_plans,
        ship_to="ship to test value",
        type=OrderType.DOMESTIC.value,
        weight=material.gross_weight,
        weight_unit=material.weight_unit,
        total_weight=material.gross_weight * quantity,
        inquiry_method=InquiryMethodType.DOMESTIC.value,
    )
    order_lines.append(line)

    return OrderLines.objects.bulk_create(order_lines)


@pytest.fixture
def es17_response():
    return {
        "piMessageId": "66013983519284311050102664329049320450",
        "salesdocument": "0412120394",
        "creditStatusText": "Credit check was not executed/Status not set",
        "data": [
            {
                "type": "fail",
                "id": "Z_EOR_ERR_ITM",
                "number": "001",
                "message": "E01 :???????????????????????????????",
                "messageV1": "000030",
                "messageV2": "E01",
                "itemNo": "000030",
            },
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
            {
                "type": "success",
                "id": "V1",
                "number": "311",
                "message": "Cash Sales Order 412120394 has been saved",
                "messageV1": "Cash Sales Order",
                "messageV2": "412120394",
                "parameter": "SALES_HEADER_IN",
                "system": "PEDCLNT039",
            },
        ],
        "orderItemsOut": [
            {
                "itemNo": "000010",
                "materialNo": "Z02KH-150D0830117N",
                "targetQuantity": 1,
                "salesUnit": "ROL",
                "plant": "7561",
                "shippingPoint": "7503",
                "route": "711191",
                "poNo": "partial_iplan_sap_in same file_02",
                "itemCategory": "ZBVN",
                "prcGroup1": "K01",
                "poDateS": "14/03/2023",
                "poItemNoS": "000010",
                "paymentTerm": "NT00",
                "netValue": 23845.5,
                "currency": "THB",
                "netWeight": 0.757,
                "grossWeight": 0.757,
                "productHierarchy": "0210KLBKH 150",
                "priceGroup": "03",
                "materialPricingGroup": "02",
                "salesDistrict": "075001",
            },
            {
                "itemNo": "000030",
                "materialNo": "Z02CA-125D1740117N",
                "targetQuantity": 1,
                "salesUnit": "ROL",
                "plant": "7561",
                "poNo": "partial_iplan_sap_in same file_02",
                "poDateS": "18/03/2023",
                "poItemNoS": "000030",
                "itemStatus": "E01",
            },
        ],
        "conditionsOut": [
            {
                "itemNo": "000010",
                "conditionStepNo": "010",
                "conditionCount": "01",
                "conditionType": "ZPR1",
                "conditionRate": 32000,
                "currency": "THB",
                "conditionUnit": "TON",
                "conditionPerUnit": 1,
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 0.757,
                "conditionExchgRate": 1,
                "numconvert": 1000,
                "denominato": 1,
                "conditionValue": 24224,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": "080",
                "conditionCount": "01",
                "conditionType": "YKD1",
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 24224,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": "090",
                "conditionCount": "01",
                "conditionType": "YKD2",
                "conditionRate": -500,
                "currency": "THB",
                "conditionUnit": "TON",
                "conditionPerUnit": 1,
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 0.757,
                "conditionExchgRate": 1,
                "numconvert": 1000,
                "denominato": 1,
                "conditionValue": -378.5,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 110,
                "conditionCount": "01",
                "conditionType": "YKD3",
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 23845.5,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 120,
                "conditionCount": "01",
                "conditionType": "YKD4",
                "currency": "THB",
                "conditionUnit": "TON",
                "conditionPerUnit": 1,
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 0.757,
                "conditionExchgRate": 1,
                "numconvert": 1000,
                "denominato": 1,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 718,
                "conditionCount": "01",
                "conditionType": "ZKD8",
                "conditionRate": -500,
                "currency": "THB",
                "conditionUnit": "TON",
                "conditionPerUnit": 1,
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 0.757,
                "conditionExchgRate": 1,
                "numconvert": 1000,
                "denominato": 1,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 719,
                "conditionCount": "01",
                "conditionType": "ZKD9",
                "currency": "THB",
                "conditionUnit": "TON",
                "conditionPerUnit": 1,
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 0.757,
                "conditionExchgRate": 1,
                "numconvert": 1000,
                "denominato": 1,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 720,
                "conditionCount": "01",
                "conditionType": "ZN00",
                "conditionRate": 23845.5,
                "currency": "THB",
                "conditionUnit": "ROL",
                "conditionPerUnit": 1,
                "conditionPriceDate": "28/12/2022",
                "conditionBaseBalue": 1,
                "conditionExchgRate": 1,
                "numconvert": 757,
                "denominato": 1,
                "conditionValue": 23845.5,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 722,
                "conditionCount": "01",
                "conditionType": "ZKD7",
                "currency": "THB",
                "conditionUnit": "TON",
                "conditionPerUnit": 1,
                "conditionPriceDate": "08/03/2023",
                "conditionBaseBalue": 0.757,
                "conditionExchgRate": 1,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 740,
                "conditionCount": "01",
                "conditionType": "MWST",
                "conditionPriceDate": "14/03/2023",
                "conditionBaseBalue": 23845.5,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 745,
                "conditionCount": "01",
                "conditionType": "ZKTX",
                "conditionRate": 7,
                "conditionPriceDate": "08/03/2023",
                "conditionBaseBalue": 23845.5,
                "conditionValue": 1669.19,
            },
            {
                "itemNo": "000010",
                "conditionStepNo": 960,
                "conditionCount": "01",
                "conditionType": "VPRS",
                "conditionRate": 18103,
                "currency": "THB",
                "conditionUnit": "KG",
                "conditionPerUnit": 1000,
                "conditionPriceDate": "08/03/2023",
                "conditionBaseBalue": 757,
                "conditionExchgRate": 1,
                "numconvert": 1,
                "denominato": 1,
                "conditionValue": 13703.97,
            },
        ],
        "orderSchedulesOut": [
            {
                "itemNo": "000010",
                "scheduleLine": "0001",
                "scheduleLineCate": "CP",
                "requestDate": "14/03/2023",
                "requestQty": 1,
                "confirmQty": 0,
            }
        ],
        "orderHeaderOut": {
            "orderAmtBeforeVat": 23845.5,
            "orderAmtVat": 1669.19,
            "orderAmtAfterVat": 25514.69,
            "currency": "THB",
        },
        "orderPartners": [
            {"partnerRole": "AG", "partnerNo": "0001007518"},
            {"partnerRole": "AP", "partnerNo": "0000032696"},
            {"partnerRole": "AU", "partnerNo": "0000000105"},
            {"partnerRole": "RE", "partnerNo": "0001007518"},
            {"partnerRole": "RG", "partnerNo": "0001007518"},
            {"partnerRole": "VE", "partnerNo": "0000000001"},
            {"partnerRole": "VE", "partnerNo": "0000000001"},
            {"partnerRole": "VE", "partnerNo": "0000000002"},
            {"partnerRole": "WE", "partnerNo": "0001010024"},
        ],
    }


@pytest.fixture
def es17_response_credit_status():
    case_status_a = {
        "piMessageId": "77860931684618376936779842006718262274",
        "salesdocument": "0410276789",
        "creditStatusCode": "A",
        "creditStatusText": "Credit check was executed, document OK",
    }
    case_status_b = {
        "piMessageId": "289475694524721282703738251087762598914",
        "salesdocument": "0410276010",
        "creditStatusCode": "B",
        "creditStatusText": "Credit check was executed, document not OK",
    }
    case_uncheck = {
        "piMessageId": "66013983519284311050102664329049320450",
        "salesdocument": "0412120394",
        "creditStatusText": "Credit check was not executed/Status not set",
    }
    return [case_status_a, case_status_b, case_uncheck]
