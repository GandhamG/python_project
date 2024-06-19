from datetime import datetime

from django.utils import timezone

from sap_master_data.models import (
    DistributionChannelMaster,
    DivisionMaster,
    SalesOrganizationMaster,
    SoldToMaster,
)
from sap_migration import models
from sap_migration.graphql.enums import OrderType


class MappingDataToObject:
    def __init__(self):
        super().__init__()
        self.contract_id = 0
        self.id = 0
        self.request_date = None

    def get_object_id_from_fields(self, models, **kwargs):
        instance = models.objects.filter(**kwargs).first()
        if instance:
            return instance.id
        else:
            raise ValueError(f"Can't found {kwargs} in {models.__name__}")

    def format_string_to_date(self, value, parse_string=False):
        format_dates = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d%m%Y"]
        for fmt in format_dates:
            try:
                date = datetime.strptime(value, fmt)
                if parse_string:
                    return date.strftime("%Y-%m-%d")
                return date
            except Exception:
                continue
        return None

    def get_create_object_id_from_fields(
        self, models, search_vals, new_vals=None, required=True
    ):
        instance = models.objects.filter(**search_vals).first()
        if instance:
            return instance.id
        if not new_vals and required:
            raise Exception(f"Can't found {search_vals} in {models.__name__}")
        if not required:
            return None
        new_obj = models(**new_vals)
        new_obj.save()
        return new_obj.id

    def map_inital_part(self, initial, header):
        _pad_number = lambda value, pad: value and value.zfill(pad) or ""
        inital_part = {
            # "createAndChangeType": initial.get("createAndChangeType"),
            "contract_type": initial.get("contractType"),
            "order_type": initial.get("orderType"),
            "sales_organization_id": self.get_object_id_from_fields(
                SalesOrganizationMaster, code=initial.get("salesOrg")
            ),
            "distribution_channel_id": self.get_object_id_from_fields(
                DistributionChannelMaster,
                code=initial.get("distributionChannel"),
            ),
            "division_id": self.get_object_id_from_fields(
                DivisionMaster, code=initial.get("division")
            ),
            # XXX: required
            "contract_id": self.get_create_object_id_from_fields(
                models.Contract,
                {"code": initial.get("contract")},
                {
                    "code": initial.get("contract"),
                    "po_no": header.get("poNo"),
                    "sold_to_code": header.get("soldTo"),
                },
            ),
            "request_delivery_date": self.format_string_to_date(
                initial.get("requestDeliveryDate")
            ),
            "sales_office_id": self.get_create_object_id_from_fields(
                models.SalesOfficeMaster,
                {
                    "code__in": (
                        initial.get("salesOffice"),
                        _pad_number(initial.get("salesOffice"), 4),
                    )
                },
            ),
            "eo_no": initial.get("eoNo"),
            "so_no": initial.get("eoNo"),
            "lot_no": initial.get("lotNo"),
        }
        self.request_date = inital_part.get("request_delivery_date")
        self.contract_id = inital_part["contract_id"]

        return inital_part

    def map_header_part(self, header):
        _pad_number = lambda value, pad: value and value.zfill(pad) or ""
        product_information = header.get("productInfomation")
        header_part = {
            "sold_to_id": self.get_create_object_id_from_fields(
                SoldToMaster,
                {
                    "sold_to_code__in": (
                        header.get("soldTo"),
                        _pad_number(header.get("soldTo"), 10),
                    )
                },
            ),
            "sold_to_code": header.get("soldTo"),
            "ship_to": header.get("shipTo"),
            # "sales_group_id": self.get_object_id_from_fields(
            #     checkout_models.SalesGroup, code=header.get("salesGroup")
            # ),
            "sales_group_id": self.get_create_object_id_from_fields(
                models.SalesGroupMaster,
                {"code": header.get("salesGroup")},
                {"code": header.get("salesGroup"), "name": header.get("salesGroup")},
            ),
            "doc_currency": header.get("docCurrency"),
            "usage": header.get("usage"),
            "unloading_point": header.get("unloadingPoint"),
            "incoterm": header.get("incoterms"),
            "place_of_delivery": header.get("placeOfDelivery"),
            "payment_term": header.get("paymentTerm"),
            "contact_person": header.get("contactPerson"),
            "author": header.get("author"),
            "bill_to": header.get("billTo"),
            "payer": header.get("payer"),
            "sales_employee": header.get("salesEmployee"),
            "internal_comment_to_warehouse": header.get("internalCommentToWarehouse"),
            "remark": header.get("remark"),
            "payment_instruction": header.get("paymentInstruction"),
            "port_of_discharge": header.get("portOfDischarge"),
            "no_of_containers": header.get("noOfContainers"),
            "shipping_mark": header.get("shippingMark"),
            # TODO: etd is date or char fields?
            "etd": header.get("ETD"),
            # XXX: eta is date field
            "eta": self.format_string_to_date(header.get("ETA")),
            "dlc_no": header.get("dlcNo"),
            "dlc_expiry_date": self.format_string_to_date(header.get("dlcExpiryDate")),
            "dlc_latest_delivery_date": self.format_string_to_date(
                header.get("dlcLatestDeliveryDate")
            ),
            "description": header.get("description"),
            "sales_email": header.get("salesEmail"),
            "cc": header.get("cc"),
            "end_customer": header.get("endCustomer"),
            "production_information": product_information,
            "uom": header.get("uom"),
            "gw_uom": header.get("gwUom"),
            "created_at": timezone.now(),
            "status_sap": "pending validate with SAP",
            "type": OrderType.EXPORT.value,
            # TODO: check this field
            "po_number": header.get("poNo"),
            "po_no": header.get("poNo"),
        }
        return header_part

    def map_item_part(self, items, order_object_id, create_and_change_type):
        item_parts_create = []
        material_codes = []
        create_and_change_type = create_and_change_type.lower()
        for item in items:
            item["materialCode"] = item.get("materialCode").replace(" ", "")
            material_codes.append(item.get("materialCode"))
        contract_material_objects = {}
        contract_material_ids = []
        material_variant_objects = {}
        material_variant_ids = []
        for contract_material in models.ContractMaterial.objects.filter(
            contract_id=self.contract_id,
            material__materialvariantmaster__code__in=material_codes,
        ):
            contract_material_objects[
                str(contract_material.material.material_code)
            ] = contract_material
            contract_material_ids.append(contract_material.id)

        for material_variant in models.MaterialVariantMaster.objects.filter(
            code__in=material_codes
        ):
            material_variant_objects[str(material_variant.code)] = material_variant
            material_variant_ids.append(material_variant.id)

        # XXX: eo-upload by load plant should work any case
        # TODO: improve this
        # if len(material_codes) != len(contract_material_objects):
        #     raise Exception("Some slugs not found")
        if create_and_change_type == "change" or create_and_change_type == "new":
            orderlines_exist = {}
            for orderline in models.OrderLines.objects.filter(
                contract_material_id__in=contract_material_ids, order_id=order_object_id
            ):
                orderlines_exist[orderline.contract_material_id] = orderline

            for item in items:
                material_variant = material_variant_objects.get(
                    item.get("materialCode")
                )
                #       # TODO: check this flow
                # if not material_variant:
                #     raise Exception(
                #         "Invalid Material Variant Master code %s"
                #         % item.get("materialCode")
                #     )
                material_code = (
                    material_variant and material_variant.material.material_code or None
                )
                contract_mat_obj = (
                    material_code
                    and contract_material_objects.get(material_code)
                    or None
                )
                # if not contract_mat_obj:
                #     raise Exception("Invalid Contract Material code %s" % material_code)
                item_part = models.OrderLines(
                    reject_reason=item.get("rejectReason"),
                    material_code=item.get("materialCode"),
                    material_variant=material_variant,
                    quantity=item.get("orderQuantity"),
                    quantity_unit=item.get("unit"),
                    item_cat_pi=item.get("itemCatPi"),
                    item_cat_eo=item.get("itemCatEo"),
                    plant=item.get("plant"),
                    condition_group1=item.get("conditionGroup1"),
                    route=item.get("route"),
                    net_price=item.get("price", 0),
                    price_currency=item.get("priceCurrency"),
                    roll_quantity=item.get("noOfRolls"),
                    roll_diameter=float(
                        str(item.get("rollDiameterInch")).replace('"', "")
                    ),
                    roll_core_diameter=float(
                        str(item.get("rollCoreDiameterInch")).replace('"', "")
                    ),
                    shipping_mark=item.get("remark"),
                    pallet_size=item.get("palletSize"),
                    roll_per_pallet=item.get("reamRollPerPallet"),
                    pallet_no=item.get("palletNo"),
                    package_quantity=item.get("noOfPackage"),
                    packing_list=item.get("packingListText"),
                    commission_percent=float(
                        str(item.get("commissionPercent")).replace('"', "")
                    )
                    if item.get("commissionPercent")
                    else 0,
                    commission_amount=float(
                        str(item.get("commission") or 0).replace('"', "")
                    ),
                    commission_unit=item.get("commissionCurrency"),
                    eo_item_no=item.get("eoItemNo"),
                    ref_pi_no=item.get("refPiStock"),
                    vat_percent=10,
                    contract_material_id=contract_mat_obj
                    and int(contract_mat_obj.id)
                    or None,
                    weight=contract_mat_obj and float(contract_mat_obj.weight) or None,
                    weight_unit=contract_mat_obj
                    and contract_mat_obj.weight_unit
                    or None,
                    type="export",
                    request_date=self.request_date,
                )
                order_qty = float(item.get("orderQuantity") or 0)
                if contract_mat_obj and order_qty > contract_mat_obj.remaining_quantity:
                    raise Exception(
                        "Order quantity is greater than Contract Material's remaining quantity (%s > %s)"
                        % (
                            order_qty,
                            contract_mat_obj.remaining_quantity or 0,
                        )
                    )
                if orderlines_exist.get(item_part.contract_material_id):
                    item_part.id = orderlines_exist.get(
                        item_part.contract_material_id
                    ).id
                    item_part.order_id = orderlines_exist.get(
                        item_part.contract_material_id
                    ).order_id
                    orderlines_exist.get(
                        item_part.contract_material_id
                    ).quantity = item_part.quantity
                    orderlines_exist.get(
                        item_part.contract_material_id
                    ).net_price = item_part.net_price
                item_parts_create.append(item_part)
        if create_and_change_type == "split":
            orderlines_exist = {}
            for orderline in models.OrderLines.objects.filter(
                contract_material_id__in=contract_material_ids,
                order_id=order_object_id,
                original_order_line_id__isnull=True,
            ):
                orderlines_exist[orderline.contract_material_id] = orderline
            for item in items:
                material_variant = material_variant_objects.get(
                    item.get("materialCode")
                )
                material_code = (
                    material_variant and material_variant.material.material_code or None
                )
                contract_mat_obj = (
                    material_code
                    and contract_material_objects.get(material_code)
                    or None
                )
                # if not contract_mat_obj:
                #     # TODO: improve the error
                #     raise ValueError("Don't have material to split")
                orderline_exist = (
                    contract_mat_obj
                    and orderlines_exist.get(int(contract_mat_obj.id))
                    or None
                )
                # if not orderline_exist:
                #     raise ValueError("Don't have material to split")
                if (
                    orderline_exist
                    and float(item.get("orderQuantity") or 0) > orderline_exist.quantity
                ):
                    raise ValueError("Can split more than original quantity")

                # if float(item.get("orderQuantity")) <= orderline_exist.quantity:
                new_item_part = models.OrderLines(
                    reject_reason=item.get("rejectReason"),
                    material_code=item.get("materialCode"),
                    original_quantity=orderlines_exist
                    and orderline_exist.quantity
                    or None,
                    material_variant=material_variant,
                    quantity=item.get("orderQuantity"),
                    quantity_unit=item.get("unit"),
                    item_cat_pi=item.get("itemCatPi"),
                    item_cat_eo=item.get("itemCatEo"),
                    plant=item.get("plant"),
                    condition_group1=item.get("conditionGroup1"),
                    route=item.get("route"),
                    net_price=item.get("price", 0),
                    price_currency=item.get("priceCurrency"),
                    roll_quantity=item.get("noOfRolls"),
                    roll_diameter=float(
                        str(item.get("rollDiameterInch")).replace('"', "")
                    ),
                    roll_core_diameter=float(
                        str(item.get("rollCoreDiameterInch")).replace('"', "")
                    ),
                    shipping_mark=item.get("remark"),
                    pallet_size=item.get("palletSize"),
                    roll_per_pallet=item.get("reamRollPerPallet"),
                    pallet_no=item.get("palletNo"),
                    package_quantity=item.get("noOfPackage"),
                    packing_list=item.get("packingListText"),
                    commission_percent=float(
                        str(item.get("commissionPercent")).replace('"', "")
                    )
                    if item.get("commissionPercent")
                    else 0,
                    commission_amount=float(
                        str(item.get("commission")).replace('"', "")
                    )
                    if item.get("commission")
                    else 0,
                    commission_unit=item.get("commissionCurrency"),
                    eo_item_no=item.get("eoItemNo"),
                    ref_pi_no=item.get("refPiStock"),
                    vat_percent=10,
                    contract_material_id=contract_mat_obj
                    and int(contract_mat_obj.id)
                    or None,
                    weight=contract_mat_obj
                    and float(contract_mat_obj.weight or 0)
                    or None,
                    weight_unit=contract_mat_obj
                    and contract_mat_obj.weight_unit
                    or None,
                    # order_id=orderline_exist.order_id,
                    original_order_line_id=orderline_exist
                    and orderline_exist.id
                    or None,
                    type="export",
                )
                if orderline_exist:
                    orderline_exist.id = orderline_exist.id
                    orderline_exist.order_id = orderline_exist.order_id
                    orderline_exist.quantity = float(orderline_exist.quantity) - float(
                        new_item_part.quantity
                    )
                    orderline_exist.net_price = float(
                        orderline_exist.net_price
                    ) - float(new_item_part.net_price)
                item_parts_create.append(new_item_part)
        return item_parts_create
