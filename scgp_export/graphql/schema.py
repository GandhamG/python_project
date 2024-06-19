import graphene

from saleor.graphql.core.connection import (
    create_connection_slice,
    filter_connection_queryset
)
from saleor.graphql.core.fields import (
    PermissionsField,
    FilterConnectionField,
)

from scg_checkout.graphql.resolves.contracts import (
    call_sap_api_get_contracts,
    sync_contract_material,
)
from scg_checkout.graphql.types import (
    SalesOrganization,
    BusinessUnit
)
from scgp_export.graphql.helper import check_input_is_contract_id_or_contract_code
from scgp_export.graphql.mutations.atp_ctp import (
    ATPCTPConfirmMutation,
    RequireAttentionATPCTPRequestMutation,
)
from scgp_export.graphql.mutations.export_atp_ctp import (
    ExportChangeOrderATPCTPRequestMutation,
    ExportChangeOrderATPCTPConfirmMutation,
)
from scgp_export.graphql.mutations.carts import (
    ExportCartCreate,
    ExportCartDraftUpdate,
    ExportCartUpdate,
    ExportCartItemsDelete,
)
from scgp_export.graphql.mutations.change_orders import ChangeExportOrderAddProducts, ChangeOrderATPCTPRequestMutation
from scgp_export.graphql.mutations.edit_order import EditExportOrderMutation
from scgp_export.graphql.mutations.orders import (
    CopyOrder,
    DeleteExportOrderLineDraft,
    ExportOrderUpdate,
    ExportOrderCreate,
    ExportOrderLineUpdate,
    ExportOrderLinesDelete,
    ExportOrderAddProducts,
    ExportOrderLineUpdateAll,
    ReceiveEoData,
    DuplicateOrder,
    CallAPISapRoute,
    CancelExportOrder,
    DownloadPDFOrder,
    ChangeParameterOfExport,
    UpdateInquiryMethodExport,
    ExportOrderLineUpdateDraft,
    UndoOrderLinesExport,
    CancelDeleteExportOrder,
    ExportAddProductToOrder,
    ExportChangeOrderAddNewOrderLine
)
from scgp_export.graphql.resolvers.carts import (
    resolve_export_pi,
    resolve_export_cart
)
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_export.graphql.resolvers.orders import (
    resolve_export_list_draft,
    resolve_export_order,
    resolve_export_order_by_so_no,
    resolve_export_orders,
    resolve_export_order_business,
    resolve_export_order_companies_by_user,
    resolve_export_order_companies_by_bu,
    resolve_export_list_orders,
    resolve_scgp_order_status,
    resolve_get_credit_limit,
)

from scgp_export.graphql.types import (
    ExportCartExtended,
    ExportCartSearchExtended,
    ExportCartDetail,
    ExportPI,
    ExportPICountableConnection,
    ExportSoldToCountableConnection,
    ExportOrderExtended,
    ExportOrderExtendedCountTableConnection,
    SalesOrganizationCountTableConnection,
    ExportOrderCountableConnection,
    ExportOrderWithAllOrderLine,
    ExportOrderAllItemBySoNo,
    StatusTypes,
    CreditLimitInput,
)
from scgp_export.graphql.filters import (
    ExportPIFilterInput,
    ExportShipToFilterInput,
    ExportCompaniesFilterInput,
    ExportSoldToFilterInput,
    ExportOrderFilterInput,
)
from scgp_export.graphql.sorters import (
    ExportPIsSortingInput,
    ExportOrderSortingInput,
)
from scgp_export.graphql.resolvers.export_pis import (
    resolve_export_pi,
    resolve_export_pis,
)
from scgp_export.graphql.resolvers.export_sold_tos import (
    resolve_export_sold_tos,
)
from scgp_export.graphql.validators import (
    required_login,
    validate_date,
)


class ExportOrderQueries(graphene.ObjectType):
    export_order = graphene.Field(ExportOrderExtended, order_id=graphene.Argument(graphene.ID))

    export_order_with_all_items = graphene.Field(ExportOrderWithAllOrderLine, order_id=graphene.Argument(graphene.ID))

    export_order_with_all_items_by_so_no = graphene.Field(ExportOrderAllItemBySoNo,
                                                          so_no=graphene.Argument(graphene.String))

    export_orders = FilterConnectionField(
        ExportOrderCountableConnection,
        sort_by=ExportOrderSortingInput(description="Sort export orders."),
        filter=ExportOrderFilterInput(description="Filtering options for export orders."),
        description="List of export orders.",
    )

    export_orders_draft = FilterConnectionField(
        ExportOrderCountableConnection,
        sort_by=ExportOrderSortingInput(description="Sort export orders."),
        filter=ExportOrderFilterInput(description="Filtering options for export orders."),
        description="List of export orders.",
    )

    filter_ship_to_export_order = FilterConnectionField(
        ExportOrderExtendedCountTableConnection,
        filter=ExportShipToFilterInput()
    )

    filter_sold_to_export_order = FilterConnectionField(
        ExportSoldToCountableConnection,
        filter=ExportSoldToFilterInput()
    )

    filter_companies_export_order_by_business_unit = FilterConnectionField(
        SalesOrganizationCountTableConnection,
        filter=ExportCompaniesFilterInput()
    )

    filter_companies_export_order_by_user_login = graphene.List(SalesOrganization)

    filter_business_export_order = graphene.List(BusinessUnit)

    scgp_order_status = graphene.List(StatusTypes)

    get_credit_limit = graphene.Field("scgp_export.graphql.types.CreditLimit",
                                      input=graphene.Argument(CreditLimitInput))

    @staticmethod
    def resolve_export_order(self, info, **kwargs):
        return resolve_export_order(kwargs.get("order_id"))

    @staticmethod
    def resolve_export_order_with_all_items(self, info, **kwargs):
        return resolve_export_order(kwargs.get("order_id"))

    @staticmethod
    def resolve_export_order_with_all_items_by_so_no(self, info, **kwargs):
        return resolve_export_order_by_so_no(info, kwargs.get("so_no"))

    @staticmethod
    def resolve_filter_ship_to_export_order(self, info, **kwargs):
        qs = resolve_export_orders()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, ExportOrderExtendedCountTableConnection
        )

    @staticmethod
    def resolve_filter_sold_to_export_order(self, info, **kwargs):
        qs = resolve_export_sold_tos()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, ExportSoldToCountableConnection)

    @staticmethod
    def resolve_filter_companies_export_order_by_business_unit(self, info, **kwargs):
        qs = resolve_export_order_companies_by_bu()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SalesOrganizationCountTableConnection
        )

    @staticmethod
    def resolve_filter_business_export_order(self, info, **kwargs):
        return resolve_export_order_business()

    @staticmethod
    def resolve_filter_companies_export_order_by_user_login(self, info, **kwargs):
        return resolve_export_order_companies_by_user()

    @staticmethod
    def resolve_export_orders(self, info, **kwargs):
        qs = resolve_export_list_orders()
        qs = filter_connection_queryset(qs, kwargs)
        filters = kwargs.get("filter")
        filters.pop("channel", None)
        last_update = filters.get("last_update", None)
        create_date = filters.get("create_date", None)

        fields = [filters.get("bu", 0), filters.get("sold_to", 0), filters.get("company", 0), filters.get("ship_to", 0)]
        fields_input = [filters.get("pi_no", 0), filters.get("po_no", 0), filters.get("eo_no", 0)]

        if any(fields):
            if not any(fields_input) and create_date is None:
                raise ValueError("Create Date must be selected")

        if (create_date or last_update) and len(filters) == 1:
            raise ValueError("Must select another criteria")

        if last_update:
            validate_date(last_update.get("gte"), last_update.get("lte"))
        if create_date:
            validate_date(create_date.get("gte"), create_date.get("lte"))

        return resolve_connection_slice(qs, info, kwargs, ExportOrderCountableConnection)

    @staticmethod
    def resolve_scgp_order_status(self, info):
        return resolve_scgp_order_status()

    @staticmethod
    def resolve_export_orders_draft(self, info, **kwargs):
        qs = resolve_export_list_draft()
        qs = filter_connection_queryset(qs, kwargs)

        return resolve_connection_slice(qs, info, kwargs, ExportOrderCountableConnection)

    @staticmethod
    def resolve_get_credit_limit(self, info, **kwargs):
        data_input = kwargs.get("input")
        return resolve_get_credit_limit(info, data_input)


class ExportSoldToQueries(graphene.ObjectType):
    export_sold_tos = FilterConnectionField(
        ExportSoldToCountableConnection,
        description="Look up export sold tos",
        filter=ExportSoldToFilterInput()
    )

    @staticmethod
    def resolve_export_sold_tos(self, info, **kwargs):
        qs = resolve_export_sold_tos()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, ExportSoldToCountableConnection
        )


class ExportPIQueries(graphene.ObjectType):
    export_pi = PermissionsField(
        ExportPI,
        description="Look up a export pi by ID",
        id=graphene.Argument(
            graphene.ID, description="ID of export pi", required=True
        ),
    )
    export_pis = FilterConnectionField(
        ExportPICountableConnection,
        description="Look up export pis",
        filter=ExportPIFilterInput(),
        sort_by=ExportPIsSortingInput()
    )

    @staticmethod
    def resolve_export_pi(self, info, **kwargs):
        id = kwargs.get("id")
        id = check_input_is_contract_id_or_contract_code(id)
        list_id = sync_contract_material(contract_id=id)
        info.variable_values.update({"list_contract_item": list_id})
        return resolve_export_pi(id)

    @staticmethod
    def resolve_export_pis(self, info, **kwargs):
        kwargs = call_sap_api_get_contracts(info, **kwargs)
        qs = resolve_export_pis(info, **kwargs)
        kwargs.get("filter").pop("sap_code")
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, ExportPICountableConnection
        )


class ExportOrderMutations(graphene.ObjectType):
    update_export_order = ExportOrderUpdate.Field()
    update_export_order_lines = ExportOrderLineUpdate.Field()
    update_all_export_order_line = ExportOrderLineUpdateAll.Field()
    create_export_order = ExportOrderCreate.Field()
    delete_export_order_lines = ExportOrderLinesDelete.Field()
    add_products_to_export_order = ExportOrderAddProducts.Field()
    add_products_to_change_export_order = ChangeExportOrderAddProducts.Field()
    receive_eo_data = ReceiveEoData.Field()
    duplicate_order = DuplicateOrder.Field()
    call_api_sap_route = CallAPISapRoute.Field()
    cancel_export_order = CancelExportOrder.Field()
    download_pdf_order = DownloadPDFOrder.Field()
    copy_order = CopyOrder.Field()
    change_parameter_of_export = ChangeParameterOfExport.Field()
    update_inquiry_method_export = UpdateInquiryMethodExport.Field()
    update_export_order_lines_draft = ExportOrderLineUpdateDraft.Field()
    export_change_order_add_product_to_order = ExportAddProductToOrder.Field()
    edit_order_export = EditExportOrderMutation.Field()
    cancel_delete_export_order = CancelDeleteExportOrder.Field()
    undo_order_lines_export = UndoOrderLinesExport.Field()
    export_change_order_add_new_order_lines = ExportChangeOrderAddNewOrderLine.Field()
    delete_export_order_line_draft = DeleteExportOrderLineDraft.Field()


class ExportCartQueries(graphene.ObjectType):
    export_carts = graphene.Field(ExportCartExtended)
    export_cart = graphene.Field(
        ExportCartDetail,
        id=graphene.Argument(graphene.ID, description='ID of ExportCart')
    )
    export_carts_search = graphene.Field(ExportCartSearchExtended)

    @staticmethod
    @required_login
    def resolve_export_carts(root, info, **kwargs):
        return ExportCartExtended()

    @staticmethod
    @required_login
    def resolve_export_cart(root, info, **kwargs):
        return resolve_export_cart(kwargs.get("id"), info.context.user.id)

    @staticmethod
    @required_login
    def resolve_export_carts_search(root, info, **kwargs):
        return ExportCartSearchExtended()


class ExportCartMutations(graphene.ObjectType):
    update_export_cart = ExportCartUpdate.Field()
    create_export_cart = ExportCartCreate.Field()
    delete_export_cart_items = ExportCartItemsDelete.Field()
    update_draft_export_cart = ExportCartDraftUpdate.Field()


class ATPCTPMutations(graphene.ObjectType):
    atp_ctp_request = RequireAttentionATPCTPRequestMutation.Field()
    change_order_atp_ctp_request = ChangeOrderATPCTPRequestMutation.Field()
    atp_ctp_confirm = ATPCTPConfirmMutation.Field()


class ExportATPCTPMutations(graphene.ObjectType):
    export_order_atp_ctp_request = ExportChangeOrderATPCTPRequestMutation.Field()
    export_order_atp_ctp_confirm = ExportChangeOrderATPCTPConfirmMutation.Field()
