import graphene
import logging
import time

from saleor.graphql.core.connection import filter_connection_queryset, create_connection_slice
from sap_master_data.graphql.types import SoldToPartnerAddressMasterCountableConnection
from scg_checkout.graphql.enums import DistributionChannelType
from scgp_cip.common.enum import PPOrderTypes, CIPOrderTypes
from scgp_cip.graphql.order.filters import CipHeaderShipTosFilterInput
from scgp_cip.graphql.order.mutations.cip_change_order import CipChangeOrderUpdate, CipSyncOrderData
from scgp_cip.graphql.order.mutations.excel_upload import ExcelUploadTemplateExport
from scgp_cip.graphql.order.resolves.orders import resolve_preview_domestic_page_order, resolve_get_order_data
from scgp_cip.graphql.order.resolves.resolves import resolve_transportation, resolve_country_master
from scgp_cip.graphql.order.types import SalesDataResponse, TempTransportation, CipTempOrder, CipPreviewOrderResponse, \
    TempCountryMaster, UnloadingPointForShipTo, CipOrderViewData, OrderTypeResponse
from scgp_cip.graphql.order.mutations.price_calculation import OrderLinePriceCalculator
from saleor.graphql.core.fields import FilterConnectionField
from scg_checkout.graphql.filters import DomesticSoldToFilterInput
from scg_checkout.graphql.types import DomesticSoldToCountableConnection, OrderEmailRecipient, EmailPendingOrder
from scgp_cip.graphql.order.resolves.sales_partner import resolve_get_sales_data, resolve_search_suggestion_ship_to_cip, \
    resolve_sold_to_header_info_cip
from scgp_cip.graphql.order.resolves.sales_partner import (resolve_search_suggestion_sold_tos_cip)
from scgp_cip.graphql.order.types import SoldToHeaderInfoType
from scgp_cip.service.change_order_service import call_es_26_and_extract_response
from scgp_cip.service.create_order_service import resolve_email_to_and_cc_by_bu_and_sold_to
from scgp_customer.graphql.resolvers.customer_contract import resolve_unloading_point

from scgp_cip.graphql.order.mutations.cip_order import CipOrderUpdate, AddCipSplitOrderLineItem, \
    AddCipSplitOrderLineAfterCp, DuplicateOrderCip
from scgp_cip.graphql.order.mutations.cp_order import CpOrderCreate
from scgp_cip.graphql.order.mutations.order_pdf_and_email import PrintOrderFromPreviewPage, SendEmailFromChangeOrder
from scgp_user_management.models import EmailConfigurationFeatureChoices
from scgp_cip.service.orders_pdf_and_email_service import get_mail_to_and_cc_list_change_order


class CIPOrderQueries(graphene.ObjectType):
    get_sales_data = graphene.Field(SalesDataResponse, sale_org=graphene.Argument(graphene.String, required=False),
                                    distribution_channel_type=graphene.Argument(DistributionChannelType,
                                                                                description="Distribution channel type",
                                                                                required=True)
                                    , description="Return logged in user sales and partner data")

    search_suggestion_sold_tos_cip = FilterConnectionField(
        DomesticSoldToCountableConnection,
        description="Look up sold tos",
        filter=DomesticSoldToFilterInput(),
        sale_org=graphene.Argument(graphene.String, required=False),
        distribution_channel=graphene.Argument(graphene.String, required=False),
        division=graphene.Argument(graphene.String, required=False),
        one_time_customer=graphene.Argument(graphene.Boolean, required=False, default_value=False)
    )
    transportation = graphene.List(
        TempTransportation,
        description="fetch transportation zone",
        country_code=graphene.Argument(graphene.String)
    )

    get_country_master_data = graphene.List(
        TempCountryMaster,
        description="fetch all available country",
    )

    get_order_data = graphene.Field(
        CipTempOrder,
        description="query to fetch order details",
        order_id=graphene.Argument(graphene.String, description="order_id of order", required=True),
    )

    preview_domestic_order = graphene.Field(
        CipPreviewOrderResponse,
        id=graphene.Argument(graphene.ID, description="ID of order", required=True),
    )

    sold_to_header_info_cip = graphene.Field(
        SoldToHeaderInfoType,
        description="Fetch sold to data",
        sold_to=graphene.Argument(graphene.String, required=False),
        sale_org=graphene.Argument(graphene.String, required=False),
        distribution_channel=graphene.Argument(graphene.String, required=False),
        division=graphene.Argument(graphene.String, required=False)
    )

    ship_to_unloading_point = graphene.Field(
        UnloadingPointForShipTo,
        description="Fetch ship to data",
        ship_to=graphene.Argument(graphene.String, required=False)
    )

    search_suggestion_ship_to = FilterConnectionField(
        SoldToPartnerAddressMasterCountableConnection,
        description="Look up domestic ship to",
        filter=CipHeaderShipTosFilterInput(),
        sold_to=graphene.Argument(graphene.String, required=False),
        sale_org=graphene.Argument(graphene.String, required=False),
        distribution_channel=graphene.Argument(graphene.String, required=False),
        division=graphene.Argument(graphene.String, required=False)
    )

    order_view_data = graphene.Field(
        CipOrderViewData,
        description="query for returning order data from es26 based on so_no in change order",
        so_no=graphene.Argument(graphene.String, description="SO No. of order", required=True),
    )

    get_order_email_to_and_cc_for_not_ref = graphene.Field(
            OrderEmailRecipient,
            sold_to_code=graphene.Argument(graphene.List(graphene.String, required=True)),
            sale_org=graphene.Argument(graphene.List(graphene.String, required=True)),
            so_no=graphene.Argument(graphene.List(graphene.String, required=True)),
    )

    get_email_to_and_cc_by_bu_and_sold_to = graphene.Field(
            EmailPendingOrder,
            sold_to_code=graphene.Argument(graphene.String, required=False),
            sale_org=graphene.Argument(graphene.String, required=False),
            bu=graphene.Argument(graphene.String, required=False),
            sale_org_list=graphene.Argument(graphene.List(graphene.String, required=False)),
    )

    list_order_types = graphene.List(
        OrderTypeResponse,
        description="List of order types for sale order page"
    )

    @staticmethod
    def resolve_list_order_types(root, info, **kwargs):
        order_types = []
        for order_type in PPOrderTypes.__enum__:
            pp_order_type = {
                "value": order_type.name,
                "label": order_type.value,
                "bu": "PP"
            }
            order_types.append(pp_order_type)
        for order_type in CIPOrderTypes.__enum__:
            cip_order_type = {
                "value": order_type.name,
                "label": order_type.value,
                "bu": "CIP"
            }
            order_types.append(cip_order_type)
        return order_types

    @staticmethod
    def resolve_transportation(self, info, **kwargs):
        try:
            transportation_data = resolve_transportation(kwargs.get("country_code"))
        except Exception as e:
            raise ValueError(f"Error fetching transportation data: {e}")

        return transportation_data

    @staticmethod
    def resolve_get_country_master_data(self, info):
        try:
            country_master_data = resolve_country_master()
        except Exception as e:
            raise ValueError(f"Error fetching country master data: {e}")
        return country_master_data

    @staticmethod
    def resolve_get_sales_data(self, info, **kwargs):
        return resolve_get_sales_data(info, kwargs)

    @staticmethod
    def resolve_search_suggestion_sold_tos_cip(self, info, **kwargs):
        return resolve_search_suggestion_sold_tos_cip(info, kwargs)

    @staticmethod
    def resolve_preview_domestic_order(self, info, **kwargs):
        return resolve_preview_domestic_page_order(info, kwargs["id"])

    @staticmethod
    def resolve_get_order_data(self, info, **kwargs):
        order_id = kwargs.get("order_id")
        return resolve_get_order_data(info, order_id)

    @staticmethod
    def resolve_search_suggestion_ship_to(self, info, **kwargs):
        qs = resolve_search_suggestion_ship_to_cip(info, kwargs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToPartnerAddressMasterCountableConnection
        )

    @staticmethod
    def resolve_sold_to_header_info_cip(self, info, **kwargs):
        return resolve_sold_to_header_info_cip(info, kwargs)

    @staticmethod
    def resolve_ship_to_unloading_point(self, info, **kwargs):
        try:
            ship_to_code = kwargs.get("ship_to", None)
            unloading_points = resolve_unloading_point(ship_to_code)

        except Exception as e:
            raise ValueError(f"Invalid Unloading Point data: {e}")
        return unloading_points

    @staticmethod
    def resolve_order_view_data(self, info, **kwargs):
        start_time = time.time()
        so_no = kwargs.get("so_no")
        logging.info(f"[No Ref Contract - View Order] For the order so_no: {so_no}, by User: {info.context.user}")
        response = call_es_26_and_extract_response(info, so_no)
        logging.info(
            f"[No Ref Contract - View Order] Time Taken to complete FE request for so_no {so_no} : {time.time() - start_time} seconds")
        return response

    @staticmethod
    def resolve_get_order_email_to_and_cc_for_not_ref(self, info, **kwargs):
        sold_to_codes = kwargs.get("sold_to_code", "")
        sale_orgs = kwargs.get("sale_org", "")
        so_no = kwargs.get("so_no", "")
        to, cc = get_mail_to_and_cc_list_change_order(sold_to_codes, sale_orgs,
                                                      EmailConfigurationFeatureChoices.ORDER_CONFIRMATION,
                                                      so_no[0])
        return {
            "to": to,
            "cc": cc,
        }

    @staticmethod
    def resolve_get_email_to_and_cc_by_bu_and_sold_to(self, info, **kwargs):
        cc, sold_to_master, to = resolve_email_to_and_cc_by_bu_and_sold_to(kwargs)
        return {
            "sold_to_name": str(sold_to_master.sold_to_name),
            "to": to,
            "cc": cc,
        }


class CIPOrderMutation(graphene.ObjectType):
    create_cip_order = CipOrderUpdate.Field()
    update_cip_order = CipOrderUpdate.Field()
    save_cip_order = CipOrderUpdate.Field()
    cp_update_create_order = CpOrderCreate.Field()
    cip_change_order_update = CipChangeOrderUpdate.Field()
    get_price_calculation = OrderLinePriceCalculator.Field()
    download_orders_pdf = PrintOrderFromPreviewPage.Field()
    add_cip_split_order_line = AddCipSplitOrderLineItem.Field()
    add_cip_split_order_line_after_cp = AddCipSplitOrderLineAfterCp.Field()
    sendEmailFromChangeOrder = SendEmailFromChangeOrder.Field()
    sync_cip_order = CipSyncOrderData.Field()
    duplicate_order_cip = DuplicateOrderCip.Field()
    export_excel_upload_template = ExcelUploadTemplateExport.Field()
