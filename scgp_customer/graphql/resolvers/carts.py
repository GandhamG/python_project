import datetime
import uuid
from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from sap_migration import models as sap_migration_models
from scg_checkout.graphql.enums import MaterialType


def resolve_customer_product(id):
    return sap_migration_models.MaterialMaster.objects.filter(id=id).first()


def resolve_customer_product_variant(product_id):
    return sap_migration_models.MaterialVariantMaster.objects.filter(product_id=product_id)


def resolve_cart(id):
    return sap_migration_models.Cart.objects.filter(id=id).first()


def resolve_customer_cart(id, info):
    cart = sap_migration_models.Cart.objects.filter(
        id=id,
        created_by=info.context.user
    ).first()

    if not cart:
        return None

    material_variants = get_cart_items_material_variant(cart, info)
    info.variable_values.update({"material_variants_sap": material_variants})
    return cart


def resolve_customer_carts(user, sold_to_id):
    opts = {"created_by": user}
    if sold_to_id:
        opts["sold_to_id"] = sold_to_id
    return sap_migration_models.Cart.objects.filter(**opts)


def resolve_cart_items(id, sort_by):
    if sort_by is None:
        return sap_migration_models.CartLines.objects.filter(cart_id=id)

    return sap_migration_models.CartLines.objects.filter(cart_id=id).order_by(
        *["{}{}".format(sort_by["direction"], field) for field in sort_by["field"]]
    )


def resolve_quantity(cart_id):
    return sap_migration_models.CartLines.objects.filter(cart_id=cart_id).count()


def resolve_customer_cart_totals(user, sold_to_id):
    total_contracts = 0
    total_products = 0
    if sold_to_id and sold_to_id.strip():
        total_contracts = sap_migration_models.Cart.objects.filter(created_by=user, sold_to_id=sold_to_id).distinct(
            "contract").count()
        total_products = sap_migration_models.CartLines.objects.filter(cart__created_by=user,
                                                                   cart__sold_to_id=sold_to_id).count()
    return {
        "total_contracts": total_contracts,
        "total_products": total_products
    }


def resolve_contract_product(info, contract_material_id):
    return sap_migration_models.ContractMaterial.objects.filter(
        id=contract_material_id
    ).first()


def resolve_contract_product_in_cart(cart_line):
    return cart_line.contract_material


def resolve_variant(cart_line):
    return cart_line.material_variant


def get_cart_items_material_variant(cart, info):
    cart_lines = sap_migration_models.CartLines.objects.filter(cart_id=cart.pk).all()
    contract_material_ids = list(map(lambda item: item.contract_material_id, cart_lines))
    contract_materials = (
        sap_migration_models.ContractMaterial.objects
        .filter(id__in=contract_material_ids)
        .all()
    )

    contract_mat_without_calling_es15 = []
    contract_mat_calling_es15 = []

    for item in contract_materials:
        if item.mat_type in MaterialType.MATERIAL_WITHOUT_VARIANT.value:
            contract_mat_without_calling_es15.append(item)
        else:
            contract_mat_calling_es15.append(item)

    material_variants = get_material_variants_by_product_from_es15(
        contract=cart.contract,
        contract_mat_call_es15=contract_mat_calling_es15,
        contract_mat_without_call_es15=contract_mat_without_calling_es15,
        sap_fn=info.context.plugins.call_api_sap_client
    )

    return material_variants


def get_material_variants_by_product_from_es15(contract, contract_mat_call_es15, contract_mat_without_call_es15,
                                               sap_fn):
    # Handle material from es15
    param = {
        "piMessageId": str(uuid.uuid1().int),
        "date": datetime.datetime.now().strftime("%d/%m/%Y"),
        "customerNo": contract.sold_to.sold_to_code,
        "product": [
            {
                "productCode": material_code
            }
            for material_code in set([item.material_code for item in contract_mat_call_es15])
        ]
    }
    uri = "sales/materials/search"
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        uri,
        param
    )
    if not response.get("data", []):
        return None

    es_15_variant_data = response.get("data")[0].get("productList", [])
    formatted_data = map_variant_data(es_15_variant_data, contract_mat_without_call_es15)

    return formatted_data


def map_variant_data(variants_call_es15, variants_not_call_es15):
    # Pull data from es15 api
    formatted_data = {
        item.get('productCode'): {
            'data_from_es15': True,
            'list_standard_variant': list(
                map(lambda material: material.get("matCode") if material.get("markFlagDelete") is not True else None,
                    item.get('matStandard', []))),
            'list_non_standard_variant': list(
                map(lambda material: material.get("matCode") if material.get("markFlagDelete") is not True else None,
                    item.get('matNonStandard', [])))
        }
        for item in variants_call_es15
    }

    # Handle data without calling ES-15
    # Since we are not calling to ES-15, a variant here will match with single material from materialmaster table
    for contract_material in variants_not_call_es15:
        formatted_data.update({
            contract_material.material_code: {
                'data_from_es15': False,
                'material_id': contract_material.material_id
            }
        })

    return formatted_data
