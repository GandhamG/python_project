from sap_migration.models import ContractMaterial, CartLines
from sap_master_data.models import Conversion2Master

TON_UNIT = "TON"
ROLL_UNIT = "ROL"


def resolve_limit_quantity(contract_id, material_id, variant_code, contract_material_id=None, info=None, calculate_cart_quantity=True, item_no="", contract_mat_id=None):
    """
    Customer confirm logic in SEO-2222 is always from TON -> KG -> ROLL
    """
    contract_mat_filter = { "id": contract_mat_id } if contract_mat_id else {
        "contract_id": contract_id,
        "material_id": material_id
    }
    if item_no:
        contract_mat_filter.update({"item_no": item_no})
    contract_mat = ContractMaterial.objects.filter(**contract_mat_filter).prefetch_related("material").first()
    if not contract_mat and info.variable_values.get("id", ""):
        cart_id = info.variable_values.get("id", "")
        contract_mat = CartLines.objects.filter(cart_id=cart_id, material_id=material_id).first().contract_material
    contract_remaining = contract_mat.remaining_quantity

    # calculate cart quantity
    cart_quantity = 0
    if calculate_cart_quantity and contract_material_id and info:
        cart = CartLines.objects.filter(contract_material_id=contract_material_id, cart__is_active=True, cart__created_by=info.context.user).first()
        if cart:
            cart_quantity = cart.quantity

    try:
        mapped_conversion = {
            record.to_unit: record
            for record in Conversion2Master.objects.filter(material_code=variant_code)
        }
        if contract_mat.material.material_group == "PK00":
            conversion_rate = 1
        else:
            conversion_rate = mapped_conversion.get(TON_UNIT).from_value / mapped_conversion.get(ROLL_UNIT).from_value
        contract_remaining = contract_remaining*conversion_rate - cart_quantity
        return round(contract_remaining, 3)
    except:
        return contract_remaining - cart_quantity


def resolve_cart_quantity(contract_id, material_id, contract_material_id=None, info=None, item_no=""):
    contract_mat_filter = {
        "contract_id": contract_id,
        "material_id": material_id
    }
    if item_no:
        contract_mat_filter.update({"item_no": item_no})

    # calculate cart quantity
    cart_quantity = 0
    if contract_material_id and info:
        cart = CartLines.objects.filter(contract_material_id=contract_material_id, cart__is_active=True, cart__created_by=info.context.user).first()
        if cart:
            cart_quantity = cart.quantity
    return cart_quantity


def resolve_weight_contract(material_code):
    try:
        mapped_conversion = Conversion2Master.objects.filter(material_code=material_code).distinct(
            "to_unit").in_bulk(field_name="to_unit")
        conversion_rate = mapped_conversion.get(ROLL_UNIT).from_value / mapped_conversion.get(TON_UNIT).from_value
        return round(conversion_rate, 3)

    except AttributeError:
        return 1
