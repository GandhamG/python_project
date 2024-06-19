import copy

import graphene
from django.db.models import Q
from graphene import ConnectionField

from saleor.core.permissions import AuthorizationFilters
from sap_master_data import models as master_models
from sap_master_data.graphql.types import SoldToPartnerAddressMasterCountableConnection
from sap_master_data.models import SalesOrganizationMaster, SoldToChannelMaster
from sap_migration.models import AlternateMaterialOs

from scg_checkout.graphql.mutations.realtime_partner import CallAPISapRealtimePartner

from saleor.graphql.account.types import UserCountableConnection
from saleor.graphql.core.connection import (
    create_connection_slice,
    filter_connection_queryset,
)
from saleor.graphql.core.fields import (
    FilterConnectionField,
    PermissionsField
)
from saleor.graphql.utils.decorators import login_required
from sap_master_data import models as master_models
from sap_master_data.graphql.types import SoldToPartnerAddressMasterCountableConnection
from sap_master_data.models import SalesOrganizationMaster
from sap_migration.graphql.types import (
    CustomerGroup1Master,
    CustomerGroup2Master,
    CustomerGroup3Master,
    CustomerGroup4Master,
    Incoterms1Master,
    SoldToMaster,
    SoldToMasterCountableConnection,
    RouteCountTableConnection,
)
from scg_checkout.graphql.mutations.realtime_partner import CallAPISapRealtimePartner
from scg_checkout.graphql.types import (
    BusinessUnit,
    BusinessUnitCountableConnection,
    ContractCheckout,
    ContractCheckoutCountableConnection,
    ContractCheckoutLineCountableConnection,
    ContractCheckoutProductVariant,
    ContractCheckoutTotal,
    DistributionChannel,
    SalesGroup,
    SalesOffice,
    SalesOrganization,
    ScgDivision,
    TempContract,
    TempContractCountableConnection,
    TempContractProduct,
    TempOrder,
    ChangeOrder,
    AlternativeMaterial,
    SoldToCountableConnection,
    AlternativeMaterialCountableConnection,
    TempOrderCountableConnection,
    TempProductCountableConnection,
    AlternatedMaterialCountableConnection,
    AlternativeMaterialOsCountableConnection,
    DomesticSoldToCountableConnection,
    DomesticMaterialCodeNameCountableConnection,
    DomesticSaleEmployeeCountableConnection,
    DomesticSalesGroupCountTableConnection,
    DomesticCompanyCountTableConnection,
    PreviewDomesticOrderLines,
    OrderEnums,
    SapMigrationCompany,
    ShowATPCTPPopup,
    OrderEmailRecipient,
    MaterialCodeDescriptionCountableConnection,
    EmailPendingOrder,
    LMSReportCSAdmin,
    GPSTracking,
    DPHyperLink,
    LMSReportCSAdminInput,
    SAPChangeOrder,
    SAPOrderConfirmationInput,
    SAPOrderConfirmation,
    CustomerBlockResponse,
    CustomerBlockInput,
    ContractCheckoutLine,
    LMSReportCSCustomer,
    LMSReportCSCustomerInput, GPSReportCSCustomer, GPSReportCSCustomerInput, GetSaleOrgDistChannelBySoldToRes,
    salesOrgSoldTo
)
from scgp_cip.common.constants import PP_SOLD_TO_ACCOUNT_GROUPS, OTC_ACCOUNT_GROUPS, CIP
from scgp_cip.service.create_order_service import resolve_email_to_and_cc_by_bu_and_sold_to
from scgp_export.graphql.helper import (
    check_input_is_contract_id_or_contract_code
)
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_export.graphql.validators import (
    validate_alternated_material_filter,
    validate_date
)
from scgp_require_attention_items.graphql.resolvers.require_attention_items import \
    resolve_material_sale_master_distinct_on_distribution_channel
from scgp_require_attention_items.graphql.types import SAPChangeOrderInput
from scgp_user_management.models import EmailConfigurationFeatureChoices
from .enums import DistributionChannelType, CustomerMaterialSoldToSearchSuggestionFilters
from .filters import (
    TempContractFilterInput,
    SuggestionMaterialFilterInput,
    AlterMaterialFilterInput,
    ScgSoldTosFilterInput,
    TempProductFilterInput,
    AlternatedMaterialFilterInput,
    SuggestionSearchUserByNameFilterInput,
    DomesticOrderFilterInput,
    DomesticSoldToFilterInput,
    DomesticMaterialCodeNameFilterInput,
    DomesticSaleEmployeeFilterInput,
    DomesticSalesGroupFilterInput,
    DomesticCompanyFilterInput,
    MaterialMasterFilterInput,
    ScgOrderDraftFilterInput,
    DomesticOrderConfirmationFilterInput,
    RouteFilterInput,
    MaterialCodeDescriptionFilterInput,
    ChangeOrderSoldToFilterInput,
    ChangeOrderShipToFilterInput,
    PendingOrderReportShipTosFilterInput,
)
from .helper import (
    get_order_id_and_so_no_of_order,
    from_response_get_lms_report_to_result,
    get_list_email_by_product_group, query_sales_org_by_sold_to, get_list_email_by_so_no
)
from .mutations.alternative_material import (
    AlternativeMaterialAdd,
    AlternativeMaterialOsDelete,
    AlternativeMaterialEdit,
    AlternativeMaterialExport,
    AlternativeMaterialLogExport,
)
from .mutations.atp_ctp import (
    CheckoutChangeOrderATPCTPRequestMutation,
    CheckoutChangeOrderATPCTPConfirmMutation
)
from .mutations.checkout import (
    ContractCheckoutCreate,
    ContractCheckoutLinesDeleteDelete,
    ContractCheckoutUpdate,
    DeleteNewlyAddedOrderLineDelete,
    CheckContractExpiredCompleteInvalid, DeleteAndSyncOrderLine,
)
from .mutations.customer_material import CustomerMaterialTemplateExport, UploadCustomerMaterials, \
    DownloadCustomerMaterialExcel
from .mutations.dtp_dtr import (
    CalculateDtpDtr,
    PostToSap
)
from .mutations.materials import UploadAlternativeMaterials
from .mutations.order import (
    AddSplitOrderLineItem,
    CheckRemainingItemQuantity,
    ContractOrderCreate,
    ContractOrderUpdate,
    ContractOrderLineDelete,
    ContractOrderLinesDelete,
    DeleteSplitOrderLineItem,
    AddProductsToDomesticOrder,
    ContractOrderLineALlUpdate,
    ContractOrderDelete,
    FinishOrder,
    ContractOrderLinesUpdate,
    CancelRevertContractOrderLine,
    PrintOrder,
    UpdateContractOrderLine,
    UpdateAtpCtpContractOrderLine,
    PrintPDFOrderConfirmation,
    SendOrderEmail,
    PrintPendingOrderReport,
    DownloadPendingOrderReportExcel,
    SendEmailPendingOrder,
    CancelDeleteOrderLines,
    ChangeOrderUpdate,
    DomesticAddProductToOrder,
    ChangeOrderAddNewOrderLine,
    UndoOrderLines
)
from .resolves.alternative_material import (
    resolve_material_alter,
    resolve_alternative_material,
    resolve_alternative_materials,
)
from .resolves.business_units import (
    resolve_business_unit,
    resolve_business_units
)
from .resolves.checkouts import (
    resolve_checkout_lines_selected,
    resolve_contract_checkout,
    resolve_contract_checkouts,
    resolve_products,
    resolve_alternated_material,
    resolve_alternative_materials_os,
    resolve_suggestion_search_user_by_name,
    resolve_product_cart_items,
    resolve_sold_to_partner_address_masters_have_partner_code
)
from .resolves.contracts import (
    resolve_contract,
    resolve_contract_product,
    resolve_contracts,
    call_sap_api_get_contracts,
    sync_contract_material,
    sync_contract_material_variant,
    resolve_routes,
    resolve_search_suggestion_domestic_sold_tos,
    resolve_search_suggestion_domestic_ship_tos,
    resolve_material_suggestion, search_suggestion_sold_tos_cust_mat, resolve_sale_organization_by_sold_to,
)
from .resolves.customer_block import resolve_get_customer_block
from .resolves.order_organization import (
    resolve_distribution_channels,
    resolve_sales_groups,
    resolve_sales_offices,
    resolve_sales_organizations,
    resolve_scg_divisions,
    resolve_distribution_channels_domestic,
    resolve_distribution_channels_export, resolve_distribution_channel_codes,
)
from .resolves.orders import (
    resolve_contract_order,
    resolve_contract_order_by_so_no,
    resolve_contract_order_by_so_no_change,
    resolve_customer_1_group,
    resolve_customer_2_group,
    resolve_customer_3_group,
    resolve_customer_4_group,
    resolve_incoterms_1,
    resolve_order_drafts,
    resolve_domestic_orders,
    resolve_domestic_sold_tos,
    resolve_domestic_material_code_name_domestic_order,
    resolve_sale_employee_domestic_order,
    resolve_filter_domestic_sales_group,
    resolve_filter_domestic_company,
    resolve_filter_domestic_business_unit,
    resolve_domestic_order_type,
    resolve_order_confirmation_status,
    resolve_domestic_order_confirmation,
    resolve_sales_organization,
    resolve_list_lms_report_cs_admin,
    resolve_get_gps_tracking,
    resolve_get_dp_hyperlink,
    resolve_sap_change_order,
    resolve_list_order_confirmation_sap,
    resolve_show_atp_ctp_popup_change_order,
    resolve_get_lms_report_cs_customer,
    resolve_get_gps_report_cs_customer
)
from .resolves.sold_tos import (
    resolve_scg_sold_to,
    resolve_scg_sold_tos,
)
from .sorters import (
    ContractsSortingInput,
    ContractCheckoutsSortingInput,
    AlternativeMaterialOsInput,
    OrderDraftSorterInput,
    DomesticOrderSortingInput,
    AlternatedMaterialSortInput,
    DomesticOrderConfirmationSortingInput
)


class CheckoutContractQueries(graphene.ObjectType):
    contracts = FilterConnectionField(
        TempContractCountableConnection,
        description="Look up scg_contract by scg_customer ID",
        sold_to_code=graphene.Argument(graphene.String, description="Code of sold to", required=True),
        contract_no=graphene.Argument(
            graphene.String, description="Code of contract"
        ),
        filter=TempContractFilterInput(),
        sort_by=ContractsSortingInput(),
    )

    contract = graphene.Field(
        TempContract,
        description="look up scg_contract",
        contract_id=graphene.Argument(graphene.ID),
        so_no=graphene.Argument(graphene.String, required=False)
    )

    material_search_suggestion = FilterConnectionField(
        TempProductCountableConnection,
        distributionChannelType=graphene.Argument(DistributionChannelType, description="Distribution channel type",
                                                  required=True),
        filter=MaterialMasterFilterInput()
    )

    get_customer_block = graphene.Field(CustomerBlockResponse, input=graphene.Argument(CustomerBlockInput))

    search_suggestion_domestic_sold_tos = FilterConnectionField(
        DomesticSoldToCountableConnection,
        description="Look up domestic sold tos",
        filter=DomesticSoldToFilterInput()
    )

    search_suggestion_domestic_ship_tos = FilterConnectionField(
        SoldToPartnerAddressMasterCountableConnection,
        description="Look up domestic ship to",
        filter=PendingOrderReportShipTosFilterInput()
    )

    @staticmethod
    def resolve_search_suggestion_domestic_ship_tos(self, info, **kwargs):
        qs = resolve_search_suggestion_domestic_ship_tos()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToPartnerAddressMasterCountableConnection
        )

    @staticmethod
    def resolve_search_suggestion_domestic_sold_tos(self, info, **kwargs):
        qs = resolve_search_suggestion_domestic_sold_tos(PP_SOLD_TO_ACCOUNT_GROUPS)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticSoldToCountableConnection
        )

    @staticmethod
    def resolve_contracts(self, info, **kwargs):
        if kwargs.get("contract_no"):
            kwargs["contract_no"] = kwargs["contract_no"].zfill(10)
        kwargs = call_sap_api_get_contracts(info, **kwargs)
        qs = resolve_contracts(info, **kwargs)
        kwargs.get("filter").pop("sap_code")
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, TempContractCountableConnection
        )

    @staticmethod
    def resolve_contract(self, info, **kwargs):
        id = kwargs.get("contract_id")
        id = check_input_is_contract_id_or_contract_code(id)
        list_id = sync_contract_material(contract_id=id)
        info.variable_values.update({"list_contract_item": list_id})
        return resolve_contract(info, id)

    @staticmethod
    def resolve_material_search_suggestion(self, info, **kwargs):
        channel_type = kwargs.get("distributionChannelType", None)
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            resolve_distribution_channel_codes(channel_type))
        qs = resolve_material_suggestion(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, TempProductCountableConnection
        )

    @staticmethod
    def resolve_get_customer_block(self, info, **kwargs):
        data_input = kwargs.get("input", None)
        sold_to_code = data_input.get("sold_to_code", None)
        contract_no = data_input.get("contract_no", None)
        if contract_no:
            contract_no = contract_no.zfill(10)
        return resolve_get_customer_block(sold_to_code, contract_no)


class CheckoutBusinessUnitQueries(graphene.ObjectType):
    business_unit = graphene.Field(
        BusinessUnit,
        description="Look up an business unit by ID.",
        id=graphene.Argument(
            graphene.ID, description="ID of business unit", required=True
        ),
    )

    business_units = FilterConnectionField(
        BusinessUnitCountableConnection, description="List of business units."
    )

    @staticmethod
    def resolve_business_units(self, info, **kwargs):
        qs = resolve_business_units()
        return create_connection_slice(
            qs, info, kwargs, BusinessUnitCountableConnection
        )

    @staticmethod
    def resolve_business_unit(self, info, **kwargs):
        return resolve_business_unit(info, kwargs.get("id"))


class ContractCheckoutQueries(graphene.ObjectType):
    contract_checkout = PermissionsField(
        ContractCheckout,
        description="Look up a checkout by ID",
        id=graphene.Argument(
            graphene.ID, description="ID of business unit", required=True
        ),
    )
    contract_checkouts = FilterConnectionField(
        ContractCheckoutCountableConnection,
        description="Look up checkouts",
        sort_by=ContractCheckoutsSortingInput(),
    )
    total_contract_checkouts = PermissionsField(
        ContractCheckoutTotal,
        description="Look up checkout",
    )

    checkout_lines_selected = FilterConnectionField(
        ContractCheckoutLineCountableConnection,
        description="Lookup checkout line selected",
        id=graphene.Argument(graphene.ID, description="ID of checkout", required=True),
    )

    contract_checkout_product_variant = PermissionsField(
        ContractCheckoutProductVariant,
        description="Look up a checkout by ID",
        id=graphene.Argument(
            graphene.ID, description="ID of business unit", required=True
        ),
    )

    @staticmethod
    def resolve_contract_checkout(self, info, **kwargs):
        id = kwargs.get("id")
        return resolve_contract_checkout(id, info)

    @login_required
    def resolve_contract_checkouts(self, info, **kwargs):
        qs = resolve_contract_checkouts(info.context.user)
        return create_connection_slice(
            qs, info, kwargs, ContractCheckoutCountableConnection
        )

    @login_required
    def resolve_total_contract_checkouts(self, info, **kwargs):
        return ContractCheckoutTotal()

    @staticmethod
    def resolve_checkout_lines_selected(self, info, **kwargs):
        id = kwargs.get("id")
        qs = resolve_checkout_lines_selected(id)
        return create_connection_slice(
            qs, info, kwargs, ContractCheckoutLineCountableConnection
        )

    @staticmethod
    def resolve_contract_checkout_product_variant(self, info, **kwargs):
        id = kwargs.get("id")
        return resolve_contract_checkout(id, info)


class ContractCheckoutMutations(graphene.ObjectType):
    create_contract_checkout = ContractCheckoutCreate.Field()
    update_contract_checkout = ContractCheckoutUpdate.Field()
    delete_contract_checkout_lines = ContractCheckoutLinesDeleteDelete.Field()
    delete_newly_added_order_line = DeleteNewlyAddedOrderLineDelete.Field()
    delete_and_sync_order_line = DeleteAndSyncOrderLine.Field()
    check_contract_expired_complete_invalid = CheckContractExpiredCompleteInvalid.Field()


class ContractOrderMutations(graphene.ObjectType):
    create_contract_order = ContractOrderCreate.Field()
    update_contract_order = ContractOrderUpdate.Field()
    delete_contract_order = ContractOrderDelete.Field()
    delete_contract_order_line = ContractOrderLineDelete.Field()
    delete_contract_order_lines = ContractOrderLinesDelete.Field()
    update_order_lines = ContractOrderLinesUpdate.Field()
    update_all_contract_order_line = ContractOrderLineALlUpdate.Field()
    cancel_revert_contract_order_line = CancelRevertContractOrderLine.Field()
    update_contract_order_line = UpdateContractOrderLine.Field()
    update_atp_ctp_contract_order_line = UpdateAtpCtpContractOrderLine.Field()

    finish_order = FinishOrder.Field()
    add_products_to_domestic_order = AddProductsToDomesticOrder.Field()
    domestic_change_order_add_product_to_order = DomesticAddProductToOrder.Field()
    add_split_order_line_item = AddSplitOrderLineItem.Field()
    delete_split_order_line_item = DeleteSplitOrderLineItem.Field()
    print_change_order = PrintOrder.Field()
    print_pdf_order_confirmation = PrintPDFOrderConfirmation.Field()
    check_remaining_item_quantity = CheckRemainingItemQuantity.Field()
    send_order_email = SendOrderEmail.Field()
    print_pending_order_report = PrintPendingOrderReport.Field()
    send_email_pending_order = SendEmailPendingOrder.Field()
    download_pending_order_report = DownloadPendingOrderReportExcel.Field()
    cancel_delete_order_lines = CancelDeleteOrderLines.Field()
    change_order_update = ChangeOrderUpdate.Field()
    change_order_add_new_order_line = ChangeOrderAddNewOrderLine.Field()
    undo_order_lines = UndoOrderLines.Field()


class CheckoutContractProductQueries(graphene.ObjectType):
    contract_product = graphene.Field(
        TempContractProduct,
        description="look up scg_contract_product",
        contract_id=graphene.Argument(graphene.ID, required=True),
        product_id=graphene.Argument(graphene.ID, required=True),
        contract_material_id=graphene.Argument(graphene.ID, required=True),
        so_no=graphene.Argument(graphene.ID, required=False)
    )

    @staticmethod
    def resolve_contract_product(self, info, **kwargs):
        product_id = kwargs.get("product_id")
        contract_id = kwargs.get("contract_id")
        contract_material_id = kwargs.get("contract_material_id")
        standard_variants, non_standard_variants = sync_contract_material_variant(
            info.context.plugins.call_api_sap_client, product_id, contract_id)
        info.variable_values.update({"list_standard_variants": standard_variants})
        info.variable_values.update({"list_non_standard_variants": non_standard_variants})
        return resolve_contract_product(info, contract_material_id)


class OrganizationQueries(graphene.ObjectType):
    sales_groups = graphene.List(
        SalesGroup,
        sale_org=graphene.Argument(graphene.String, description="Code of sale organization")
    )
    sales_offices = graphene.List(
        SalesOffice,
        sale_org=graphene.Argument(graphene.String, description="Code of sale organization")
    )
    scg_divisions = graphene.List(ScgDivision)
    distribution_channels = graphene.List(DistributionChannel)
    sales_organizations = graphene.List(SalesOrganization)
    distribution_channels_domestic = graphene.List(DistributionChannel)
    distribution_channels_export = graphene.List(DistributionChannel)

    @staticmethod
    def resolve_sales_groups(self, info, **kwargs):
        sale_org_code = kwargs.get("sale_org", None)
        return resolve_sales_groups(sale_org_code)

    @staticmethod
    def resolve_sales_offices(self, info, **kwargs):
        sale_org_code = kwargs.get("sale_org", None)
        return resolve_sales_offices(sale_org_code)

    @staticmethod
    def resolve_scg_divisions(self, info, **kwargs):
        return resolve_scg_divisions()

    @staticmethod
    def resolve_distribution_channels(self, info, **kwargs):
        return resolve_distribution_channels()

    @staticmethod
    def resolve_sales_organizations(self, info, **kwargs):
        return resolve_sales_organizations()

    @staticmethod
    def resolve_distribution_channels_domestic(self, info, **kwargs):
        return resolve_distribution_channels_domestic()

    @staticmethod
    def resolve_distribution_channels_export(self, info, **kwargs):
        return resolve_distribution_channels_export()


class ContractOrderQueries(graphene.ObjectType):
    contract_order = graphene.Field(
        TempOrder,
        description="query order by SO No. order",
        so_no=graphene.Argument(graphene.String, description="SO No. of order", required=True),
    )

    change_order = graphene.Field(
        ChangeOrder,
        description="query order by SO No. order",
        so_no=graphene.Argument(graphene.String, description="SO No. of order", required=True),
    )

    order_drafts = FilterConnectionField(
        TempOrderCountableConnection,
        description="Look up order_drafts",
        sort_by=OrderDraftSorterInput(),
        filter=ScgOrderDraftFilterInput()
    )

    filter_sold_to_domestic_order = FilterConnectionField(
        DomesticSoldToCountableConnection,
        filter=DomesticSoldToFilterInput()
    )

    filter_material_code_name_domestic_order = FilterConnectionField(
        DomesticMaterialCodeNameCountableConnection,
        distributionChannelType=graphene.Argument(DistributionChannelType, description="Distribution channel type",
                                                  required=True),
        filter=DomesticMaterialCodeNameFilterInput()
    )
    filter_sale_employee_domestic_order = FilterConnectionField(
        DomesticSaleEmployeeCountableConnection,
        filter=DomesticSaleEmployeeFilterInput()
    )
    filter_domestic_business_unit = graphene.List(BusinessUnit)

    filter_domestic_company_by_bu = FilterConnectionField(
        DomesticCompanyCountTableConnection,
        filter=DomesticCompanyFilterInput()
    )

    filter_domestic_sales_group_by_company = FilterConnectionField(
        DomesticSalesGroupCountTableConnection,
        filter=DomesticSalesGroupFilterInput()
    )

    domestic_order_type = ConnectionField(TempOrderCountableConnection)

    domestic_orders = FilterConnectionField(
        TempOrderCountableConnection,
        sort_by=DomesticOrderSortingInput(description="Sort domestic orders."),
        filter=DomesticOrderFilterInput(description="Filtering options for domestic orders."),
        description="List of domestic orders.",
    )

    preview_domestic_page_order = graphene.Field(
        PreviewDomesticOrderLines,
        id=graphene.Argument(graphene.ID, description="ID of order", required=True),
    )

    order_confirmation_status = graphene.List(OrderEnums)

    domestic_order_confirmation = FilterConnectionField(
        TempOrderCountableConnection,
        sort_by=DomesticOrderConfirmationSortingInput(description="Sort order confirmation."),
        filter=DomesticOrderConfirmationFilterInput(description="Filtering options for order confirmation"),
    )

    filter_domestic_order_confirmation_company = graphene.List(SapMigrationCompany)

    get_order_email_to_and_cc = graphene.Field(
        OrderEmailRecipient,
        sold_to_code=graphene.Argument(graphene.List(graphene.String, required=True)),
        sale_org=graphene.Argument(graphene.List(graphene.String, required=True)),
        so_no=graphene.Argument(graphene.List(graphene.String, required=True)),
        bu=graphene.Argument(graphene.String, required=False),
    )

    get_email_to_and_cc_by_sold_to = graphene.Field(
        EmailPendingOrder,
        sold_to_code=graphene.Argument(graphene.String, required=True),
        sale_org=graphene.Argument(graphene.String, required=False),
        product_group=graphene.Argument(graphene.List(graphene.String, required=False)),
        sale_org_list=graphene.Argument(graphene.List(graphene.String, required=False)),
        bu=graphene.Argument(graphene.String, required=False),
    )

    get_sales_org_by_sold_to = graphene.List(salesOrgSoldTo,
                                             sold_to_code=graphene.Argument(graphene.String, required=False))

    list_lms_report_cs_admin = graphene.List(
        LMSReportCSAdmin,
        filter=graphene.Argument(LMSReportCSAdminInput)
    )

    get_gps_tracking = graphene.Field(
        GPSTracking,
        gps_tracking=graphene.Argument(graphene.String, required=True),
    )

    get_dp_hyperlink = graphene.Field(
        DPHyperLink,
        dp_no=graphene.Argument(graphene.String, required=True),
    )
    list_order_confirmation_sap = graphene.List(
        SAPOrderConfirmation,
        filter=graphene.Argument(SAPOrderConfirmationInput)
    )

    get_lms_report_cs_customer = graphene.List(
        LMSReportCSCustomer,
        description="Get LMS Report CS/Customer",
        filter=graphene.Argument(LMSReportCSCustomerInput)
    )

    get_gps_report_cs_customer = graphene.List(
        GPSReportCSCustomer,
        description="Get LMS GPS  Report CS/Customer",
        filter=graphene.Argument(GPSReportCSCustomerInput)
    )

    @staticmethod
    def resolve_list_order_confirmation_sap(self, info, **kwargs):
        data_input = kwargs.get('filter')
        return resolve_list_order_confirmation_sap(data_input, info)

    sap_change_order = graphene.List(
        SAPChangeOrder,
        filter=graphene.Argument(SAPChangeOrderInput)
    )

    suggestion_sold_to_change_order_search = FilterConnectionField(
        SoldToPartnerAddressMasterCountableConnection,
        filter=ChangeOrderSoldToFilterInput()
    )

    suggestion_ship_to_change_order_search = FilterConnectionField(
        SoldToPartnerAddressMasterCountableConnection,
        filter=ChangeOrderShipToFilterInput()
    )

    @staticmethod
    def resolve_suggestion_sold_to_change_order_search(self, info, **kwargs):
        qs = resolve_sold_to_partner_address_masters_have_partner_code()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToPartnerAddressMasterCountableConnection
        )

    @staticmethod
    def resolve_suggestion_ship_to_change_order_search(self, info, **kwargs):
        qs = resolve_sold_to_partner_address_masters_have_partner_code()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToPartnerAddressMasterCountableConnection
        )

    @staticmethod
    def resolve_sap_change_order(self, info, **kwargs):
        input_from_user = kwargs.get('filter')
        return resolve_sap_change_order(input_from_user, info)

    @staticmethod
    def resolve_filter_domestic_order_confirmation_company(self, info, **kwargs):
        return resolve_filter_domestic_company()

    @staticmethod
    def resolve_contract_order(self, info, **kwargs):
        so_no = kwargs.get("so_no")
        # TODO: improve this
        if len(so_no) < 10:
            return resolve_contract_order(info, so_no)
        return resolve_contract_order_by_so_no(info, so_no)

    @staticmethod
    def resolve_change_order(self, info, **kwargs):
        so_no = kwargs.get("so_no")
        return resolve_contract_order_by_so_no_change(info, so_no)

    @staticmethod
    def resolve_order_drafts(self, info, **kwargs):
        qs = resolve_order_drafts(info.context.user)
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, TempOrderCountableConnection
        )

    @staticmethod
    def resolve_filter_domestic_business_unit(self, info, **kwargs):
        return resolve_filter_domestic_business_unit()

    @staticmethod
    def resolve_filter_domestic_sales_group_by_company(self, info, **kwargs):
        qs = resolve_filter_domestic_sales_group()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticSalesGroupCountTableConnection
        )

    @staticmethod
    def resolve_filter_domestic_company_by_bu(self, info, **kwargs):
        qs = resolve_filter_domestic_company()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticCompanyCountTableConnection
        )

    @staticmethod
    def resolve_filter_sale_employee_domestic_order(self, info, **kwargs):
        qs = resolve_sale_employee_domestic_order()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticSaleEmployeeCountableConnection)

    @staticmethod
    def resolve_filter_material_code_name_domestic_order(self, info, **kwargs):
        channel_type = kwargs.get("distributionChannelType", None)
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            resolve_distribution_channel_codes(channel_type))
        qs = resolve_domestic_material_code_name_domestic_order(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticMaterialCodeNameCountableConnection)

    @staticmethod
    def resolve_filter_sold_to_domestic_order(self, info, **kwargs):
        qs = resolve_domestic_sold_tos()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticSoldToCountableConnection)

    @staticmethod
    def resolve_domestic_order_type(self, info, **kwargs):
        qs = resolve_domestic_order_type()
        return create_connection_slice(
            qs, info, kwargs, TempOrderCountableConnection)

    @staticmethod
    def resolve_domestic_orders(self, info, **kwargs):
        qs = resolve_domestic_orders()
        qs = filter_connection_queryset(qs, kwargs)
        filters = kwargs.get("filter")
        filters.pop("channel", None)
        last_update = filters.get("last_update", None)
        create_date = filters.get("create_date", None)
        if last_update:
            validate_date(last_update.get("gte"), last_update.get("lte"))
        if create_date:
            validate_date(create_date.get("gte"), create_date.get("lte"))
        return resolve_connection_slice(qs, info, kwargs, TempOrderCountableConnection)

    @staticmethod
    def resolve_preview_domestic_page_order(self, info, **kwargs):
        order_id, so_no = get_order_id_and_so_no_of_order(kwargs["id"])
        # response = call_sap_es26(so_no=so_no, sap_fn=info.context.plugins.call_api_sap_client)
        # sync_export_order_from_es26(response)
        return resolve_contract_order(info, order_id)

    @staticmethod
    def resolve_order_confirmation_status(self, info, **kwargs):
        return resolve_order_confirmation_status()

    @staticmethod
    def resolve_domestic_order_confirmation(self, info, **kwargs):
        qs = resolve_domestic_order_confirmation()
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, TempOrderCountableConnection)

    @staticmethod
    def resolve_get_order_email_to_and_cc(self, info, **kwargs):
        sold_to_codes = kwargs.get("sold_to_code", "")
        sale_orgs = kwargs.get("sale_org", "")
        so_no = kwargs.get("so_no", "")
        bu = kwargs.get("bu", "")
        to, cc = get_list_email_by_so_no(sold_to_codes, sale_orgs, bu,
                                         EmailConfigurationFeatureChoices.ORDER_CONFIRMATION, so_no)
        return {
            "to": to,
            "cc": cc,
        }

    @staticmethod
    def resolve_get_sales_org_by_sold_to(self, info, **kwargs):
        sold_to_code = kwargs.get("sold_to_code", "")
        return query_sales_org_by_sold_to(sold_to_code)

    @staticmethod
    def resolve_get_email_to_and_cc_by_sold_to(self, info, **kwargs):
        sold_to_code = kwargs.get("sold_to_code", "")
        sale_org_code = kwargs.get("sale_org_list", [])
        product_group = kwargs.get("product_group", "")
        bu = kwargs.get("bu", "")
        to, cc = get_list_email_by_product_group([sold_to_code], sale_org_code, bu,
                                                 EmailConfigurationFeatureChoices.PENDING_ORDER, product_group)
        sold_to_master = master_models.SoldToMaster.objects.filter(sold_to_code=sold_to_code).first()
        return {
            "sold_to_name": str(sold_to_master.sold_to_name),
            "to": to,
            "cc": cc,
        }

    @staticmethod
    def resolve_list_lms_report_cs_admin(self, info, **kwargs):
        data_filter = kwargs.get("filter")
        return resolve_list_lms_report_cs_admin(data_filter, info)

    @staticmethod
    def resolve_get_gps_tracking(self, info, **kwargs):
        gps_tracking = kwargs.get("gps_tracking")
        return resolve_get_gps_tracking(gps_tracking, info)

    @staticmethod
    def resolve_get_dp_hyperlink(self, info, **kwargs):
        dp_no = kwargs.get("dp_no")
        return resolve_get_dp_hyperlink(dp_no, info)

    @staticmethod
    def resolve_get_lms_report_cs_customer(self, info, **kwargs):
        data_filter = kwargs.get("filter")
        response = resolve_get_lms_report_cs_customer(info, data_filter)
        return from_response_get_lms_report_to_result(response)

    @staticmethod
    def resolve_get_gps_report_cs_customer(self, info, **kwargs):
        data_filter = kwargs.get("filter")
        response = resolve_get_gps_report_cs_customer(info, data_filter)
        return from_response_get_lms_report_to_result(response)


class ScgSoldToQueries(graphene.ObjectType):
    scg_sold_to = graphene.Field(
        SoldToMaster,
        description="query scg sold to by id",
        id=graphene.Argument(graphene.ID, description="ID of sold to", required=True),
    )
    scg_sold_tos = FilterConnectionField(
        SoldToMasterCountableConnection,
        filter=ScgSoldTosFilterInput()
    )

    @staticmethod
    def resolve_scg_sold_to(self, info, **kwargs):
        pk = kwargs.get("id")
        return resolve_scg_sold_to(pk)

    @staticmethod
    def resolve_scg_sold_tos(self, info, **kwargs):
        qs = resolve_scg_sold_tos()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToCountableConnection
        )


class AlternativeMaterialMutations(graphene.ObjectType):
    delete_alternative_material_os = AlternativeMaterialOsDelete.Field()
    add_alternative_material = AlternativeMaterialAdd.Field()
    edit_alternative_material = AlternativeMaterialEdit.Field()
    export_alternative_material = AlternativeMaterialExport.Field()
    export_Log_Change = AlternativeMaterialLogExport.Field()


class AlternativeMaterialQueries(graphene.ObjectType):
    suggestion_search_material = FilterConnectionField(
        TempProductCountableConnection,
        distributionChannelType=graphene.Argument(DistributionChannelType, description="Distribution channel type",
                                                  required=True),
        filter=SuggestionMaterialFilterInput(),
    )

    alternative_materials_os = FilterConnectionField(
        AlternativeMaterialOsCountableConnection,
        filter=AlterMaterialFilterInput(),
        sort_by=AlternativeMaterialOsInput(),
    )

    alternated_materials = FilterConnectionField(
        AlternatedMaterialCountableConnection,
        filter=AlternatedMaterialFilterInput(),
        sort_by=AlternatedMaterialSortInput(),
        description="log change material"
    )

    material_alter = FilterConnectionField(
        TempProductCountableConnection,
        distributionChannelType=graphene.Argument(DistributionChannelType, description="Distribution channel type",
                                                  required=True),
        filter=TempProductFilterInput()
    )

    suggestion_search_user_by_name = FilterConnectionField(
        UserCountableConnection,
        filter=SuggestionSearchUserByNameFilterInput()
    )

    alternative_material = PermissionsField(
        AlternativeMaterial,
        description="Look up alternative material",
        id=graphene.Argument(
            graphene.ID, description="ID of alternative material", required=True
        ),
    )

    @staticmethod
    def resolve_suggestion_search_material(root, info, **kwargs):
        channel_type = kwargs.get("distributionChannelType", None)
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            resolve_distribution_channel_codes(channel_type))
        qs = resolve_products(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(qs, info, kwargs, TempProductCountableConnection)

    @staticmethod
    def resolve_alternated_materials(root, info, **kwargs):
        validate_alternated_material_filter(kwargs)
        qs = resolve_alternated_material()
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(qs, info, kwargs, AlternatedMaterialCountableConnection)

    @staticmethod
    def resolve_alternative_materials_os(root, info, **kwargs):
        kwargs_copy = copy.deepcopy(kwargs)
        qs = resolve_alternative_materials_os(kwargs_copy)
        qs = filter_connection_queryset(qs, kwargs_copy)
        return resolve_connection_slice(qs, info, kwargs_copy, AlternativeMaterialOsCountableConnection)

    @staticmethod
    def resolve_material_alter(self, info, **kwargs):
        channel_type = kwargs.get("distributionChannelType", None)
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            resolve_distribution_channel_codes(channel_type))
        qs = resolve_material_alter(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, TempProductCountableConnection
        )

    @staticmethod
    def resolve_alternative_material(self, info, **kwargs):
        id = kwargs.get("id")
        return resolve_alternative_material(id)

    @staticmethod
    def resolve_suggestion_search_user_by_name(root, info, **kwargs):
        qs = resolve_suggestion_search_user_by_name()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, UserCountableConnection
        )


class ScgMaterialQueries(graphene.ObjectType):
    alternative_materials = FilterConnectionField(
        AlternativeMaterialCountableConnection, description="List alternative materials."
    )

    @staticmethod
    def resolve_alternative_materials(self, info, **kwargs):
        qs = resolve_alternative_materials()
        return resolve_connection_slice(
            qs, info, kwargs, AlternativeMaterialCountableConnection
        )


class ScgMaterialMutations(graphene.ObjectType):
    upload_alternative_materials = UploadAlternativeMaterials.Field()


class DtpDtrMutations(graphene.ObjectType):
    calculate_dtp_dtr = CalculateDtpDtr.Field()
    post_to_sap = PostToSap.Field()


class RealtimePartnerMutations(graphene.ObjectType):
    get_sap_realtime_partner = CallAPISapRealtimePartner.Field()


class CustomerGroupMasterQueries(graphene.ObjectType):
    customer_group_1 = graphene.List(CustomerGroup1Master)
    customer_group_2 = graphene.List(CustomerGroup2Master)
    customer_group_3 = graphene.List(CustomerGroup3Master)
    customer_group_4 = graphene.List(CustomerGroup4Master)

    @staticmethod
    def resolve_customer_group_1(root, info, **kwargs):
        qs = resolve_customer_1_group()
        return qs

    @staticmethod
    def resolve_customer_group_2(root, info, **kwargs):
        qs = resolve_customer_2_group()
        return qs

    @staticmethod
    def resolve_customer_group_3(root, info, **kwargs):
        qs = resolve_customer_3_group()
        return qs

    @staticmethod
    def resolve_customer_group_4(root, info, **kwargs):
        qs = resolve_customer_4_group()
        return qs


class IncotermMasterQueries(graphene.ObjectType):
    incoterms_1 = graphene.List(Incoterms1Master)

    @staticmethod
    def resolve_incoterms_1(root, info, **kwargs):
        return resolve_incoterms_1()


class ATPCTPQueries(graphene.ObjectType):
    show_atp_ctp_popup = graphene.Field(
        ShowATPCTPPopup,
        description="Can show atp ctp popup.",
        line_ids=graphene.List(graphene.ID, description="List of order line ids")
    )

    @staticmethod
    def resolve_show_atp_ctp_popup(self, info, **kwargs):
        line_ids = kwargs.get("line_ids")
        return resolve_show_atp_ctp_popup_change_order(line_ids)


class RouteQueries(graphene.ObjectType):
    routes = FilterConnectionField(
        RouteCountTableConnection,
        filter=RouteFilterInput()
    )

    @staticmethod
    def resolve_routes(self, info, **kwargs):
        qs = resolve_routes()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RouteCountTableConnection
        )


class DeliveryReportQueries(graphene.ObjectType):
    delivery_sold_to = FilterConnectionField(
        DomesticSoldToCountableConnection,
        filter=DomesticSoldToFilterInput()
    )

    delivery_material_code_description = FilterConnectionField(
        MaterialCodeDescriptionCountableConnection,
        filter=MaterialCodeDescriptionFilterInput()
    )

    delivery_sales_organization = graphene.List(SalesOrganization)

    @staticmethod
    def resolve_delivery_sold_to(self, info, **kwargs):
        qs = resolve_domestic_sold_tos()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticSoldToCountableConnection)

    @staticmethod
    def resolve_delivery_material_code_description(self, info, **kwargs):
        user = info.context.user
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            get_distribution_channel_code_by_user_group(user))
        qs = resolve_domestic_material_code_name_domestic_order(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticMaterialCodeNameCountableConnection)

    @staticmethod
    def resolve_delivery_sales_organization(self, info, **kwargs):
        return resolve_sales_organization()


class CartItemsQueries(graphene.ObjectType):
    cart_product_items = PermissionsField(
        graphene.List(ContractCheckoutLine),
        sold_to_code=graphene.String(required=True),
        contract_code=graphene.String(required=True),
        permissions=[AuthorizationFilters.AUTHENTICATED_USER],
    )

    @staticmethod
    def resolve_cart_product_items(root, info, **kwargs):
        user = info.context.user
        sold_to_code = kwargs["sold_to_code"]
        contract_code = kwargs["contract_code"]
        return resolve_product_cart_items(user, sold_to_code, contract_code)


class CheckoutATPCTPMutations(graphene.ObjectType):
    checkout_atp_ctp_request = CheckoutChangeOrderATPCTPRequestMutation.Field()
    checkout_atp_ctp_confirm = CheckoutChangeOrderATPCTPConfirmMutation.Field()


class CustomerMaterialMutations(graphene.ObjectType):
    export_customer_material_template = CustomerMaterialTemplateExport.Field()
    upload_customer_materials = UploadCustomerMaterials.Field()
    download_customer_material_excel = DownloadCustomerMaterialExcel.Field()


class CustomerMaterialQueries(graphene.ObjectType):
    search_suggestion_sold_tos_cust_mat = FilterConnectionField(
        DomesticSoldToCountableConnection,
        description="Look up customer material sold tos",
        filter=DomesticSoldToFilterInput()
    )
    get_sale_org_and_dist_channel_by_sold_to = graphene.Field(
        GetSaleOrgDistChannelBySoldToRes,
        description="query to fetch sale org and distribution channel by sold to",
        sold_to=graphene.Argument(graphene.String, required=True),
    )

    @staticmethod
    def resolve_search_suggestion_sold_tos_cust_mat(self, info, **kwargs):
        qs = search_suggestion_sold_tos_cust_mat(CustomerMaterialSoldToSearchSuggestionFilters.ACCOUNT_GROUPS.value,
                                                 CustomerMaterialSoldToSearchSuggestionFilters.DISTRIBUTION_CHANNEL.value)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, DomesticSoldToCountableConnection
        )

    @staticmethod
    def resolve_get_sale_org_and_dist_channel_by_sold_to(self, info, **kwargs):
        sold_to = kwargs.get("sold_to")
        return resolve_sale_organization_by_sold_to(sold_to)
