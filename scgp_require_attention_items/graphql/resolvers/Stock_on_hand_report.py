import uuid

from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from scgp_require_attention_items.graphql.helper import mapping_ipan_65201_response
from sap_migration.models import MaterialVariantMaster
from sap_master_data.models import MaterialMaster


def resolve_get_stock_on_hand_report(root, info, **kwargs):
    data_input = kwargs.get("input")
    code = data_input.get("code")
    product = MaterialVariantMaster.objects.filter(code=code).first()
    if not product:
        product = MaterialMaster.objects.filter(material_code=code).first()
    if not product:
        raise ValueError("Invalid material code " + code)

    body = {
        "inquiry_Id": str(uuid.uuid1().int),  # Mock data
        "unit": data_input.get("unit"),  # Mock data
    }

    try:
        api_response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value).request_mulesoft_get(
            f"sales/available-to-promise/stock/{code}",
            body
        )
        on_hand_cs_inquiry_response = api_response.get("OnHandCSInquiryResponse", {})

        if on_hand_cs_inquiry_response.get("returnStatus", "").upper() == "FAILURE":
            raise ValueError(on_hand_cs_inquiry_response.get("returnCode",
                                                             "1") + " - " + on_hand_cs_inquiry_response.get(
                "returnCodeDescription", ""))

    except Exception as e:
        raise ValueError(e)
    return mapping_ipan_65201_response(api_response, f"{code} / {product.description_en}")
