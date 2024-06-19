import graphene

from saleor.graphql.core.connection import create_connection_slice, filter_connection_queryset
from saleor.graphql.core.fields import FilterConnectionField, PermissionsField
from saleor.graphql.utils.decorators import login_required
from scg_checkout.graphql.enums import DistributionChannelType
from scg_checkout.graphql.resolves.contracts import (
    call_sap_api_get_customer_contracts,
    sync_contract_material,
    sync_contract_material_variant,
)
from scg_checkout.graphql.resolves.order_organization import resolve_distribution_channel_codes
from scgp_customer.graphql.mutations.orders import (
    CustomerOrderUpdate,
    CreateCustomerOrder,
    CustomerOrderLinesDelete,
    CustomerOrderAddProduct,
    CustomerOrderLinesUpdate,
    UpdateRequestDateOnIplan,
)
from scgp_customer.graphql.mutations.carts import CartItemsDelete
from scgp_customer.graphql.resolvers.customer_contract import (
    resolve_contract,
    resolve_scgp_customer_contracts,
    resolve_unloading_point,
)
from scgp_customer.graphql.resolvers.carts import (
    resolve_customer_carts,
    resolve_customer_cart,
    resolve_customer_cart_totals,
)
from scgp_customer.graphql.resolvers.customer_report import resolve_customer_lms_report
from scgp_customer.graphql.types import (
    CustomerCart,
    CustomerCartCountableConnection,
    CustomerCartProductVariant,
    CustomerCartTotals,
    CustomerContract,
    CustomerContractProduct,
    CustomerContractCountableConnection,
    CustomerUnloadingPoint,
    PreviewOrderLines,
    CustomerOrderExtended,
    CustomerOrderCountTableConnection,
    CustomerMaterialCodeNameCountTableConnection,
    CustomerCompanyCountTableConnection,
    CustomerSalesGroupCountTableConnection,
    CustomerBusinessUnit,
    CustomerCompany,
    SAPOrderMapping,
    LmsReportCustomer,
    CustomerLmsReportInput,
)
from scgp_customer.graphql.sorters import (
    CustomerCartsSortingInput,
    CustomerOrderSortingInput,
    CustomerOrderConfirmationSortingInput
)
from scgp_customer.graphql.mutations.carts import (
    CustomerCartCreate,
    CustomerCartUpdate,
    CustomerCartLinesUpdateQuantity
)
from scgp_customer.graphql.resolvers.carts import resolve_contract_product
from scgp_customer.graphql.resolvers.orders import (
    resolve_customer_order,
    resolve_customer_orders,
    resolve_filter_material_code_name_customer_order,
    resolve_filter_customer_business_unit,
    resolve_filter_customer_company_by_bu,
    resolve_filter_customer_sales_group,
    resolve_customer_order_confirmation,
    resolve_filter_customer_order_confirmation_company,
    resolve_customer_orders_from_sap,
)
from scgp_customer.graphql.filters import (
    CustomerContractFilterInput,
    CustomerContractsSortingInput,
    CustomerOrderFilterInput,
    CustomerMaterialCodeNameFilterInput,
    CustomerCompanyFilterInput,
    CustomerSalesGroupFilterInput,
    CustomerOrderConfirmationFilterInput,
)
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_export.graphql.validators import validate_date
from scgp_require_attention_items.graphql.resolvers.require_attention_items import \
    resolve_material_sale_master_distinct_on_distribution_channel


class SAPOrderRequest(graphene.InputObjectType):
    sold_to = graphene.String()
    material_code = graphene.String()
    so_no = graphene.String()
    contract_no = graphene.String()
    dp_no = graphene.String()
    invoice_no = graphene.String()
    bu = graphene.String()
    company = graphene.String()
    create_date_from = graphene.Date()
    create_date_to = graphene.Date()
    update_date_from = graphene.Date()
    update_date_to = graphene.Date()
    purchase_order_no = graphene.String()


class CustomerOrderQueries(graphene.ObjectType):
    customer_order = graphene.Field(CustomerOrderExtended, order_id=graphene.Argument(graphene.ID))

    preview_customer_order = graphene.Field(
        PreviewOrderLines,
        id=graphene.Argument(graphene.ID, description="ID of order", required=True),
    )

    @staticmethod
    def resolve_preview_customer_order(self, info, **kwargs):
        return resolve_customer_order(kwargs.get("id"))

    filter_material_code_name_customer_order = FilterConnectionField(
        CustomerMaterialCodeNameCountTableConnection,
        distributionChannelType=graphene.Argument(DistributionChannelType, description="Distribution channel type",
                                                  required=True),
        filter=CustomerMaterialCodeNameFilterInput()
    )
    filter_customer_business_unit = graphene.List(CustomerBusinessUnit)

    filter_customer_company_by_bu = FilterConnectionField(
        CustomerCompanyCountTableConnection,
        filter=CustomerCompanyFilterInput()
    )

    filter_customer_sales_group_by_company = FilterConnectionField(
        CustomerSalesGroupCountTableConnection,
        filter=CustomerSalesGroupFilterInput()
    )

    customer_orders = FilterConnectionField(
        CustomerOrderCountTableConnection,
        sort_by=CustomerOrderSortingInput(description="Sort customer orders."),
        filter=CustomerOrderFilterInput(description="Filtering options for customer orders"),
        description="List of customer orders.",
    )

    customer_order_confirmation = FilterConnectionField(
        CustomerOrderCountTableConnection,
        sort_by=CustomerOrderConfirmationSortingInput(description="Sort order confirmation."),
        filter=CustomerOrderConfirmationFilterInput(description="Filtering options for order confirmation"),
    )

    filter_customer_order_confirmation_company = graphene.List(CustomerCompany)

    customer_orders_from_sap = graphene.List(
        SAPOrderMapping,
        description="Customer orders from SAP.",
        input=graphene.Argument(SAPOrderRequest)
    )

    @staticmethod
    def resolve_filter_customer_order_confirmation_company(self, info, **kwargs):
        return resolve_filter_customer_order_confirmation_company()

    @staticmethod
    def resolve_customer_order(self, info, **kwargs):
        return resolve_customer_order(kwargs.get("order_id"))

    @staticmethod
    def resolve_filter_customer_business_unit(self, info, **kwargs):
        dicts = resolve_filter_customer_business_unit()
        for item in dicts:
            if item.get("code") == "PP":
                item["is_default_for_inquiry_search"] = True
        return dicts

    @staticmethod
    def resolve_filter_customer_company_by_bu(self, info, **kwargs):
        qs = resolve_filter_customer_company_by_bu()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, CustomerCompanyCountTableConnection
        )

    @staticmethod
    def resolve_filter_customer_sales_group_by_company(self, info, **kwargs):
        qs = resolve_filter_customer_sales_group()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, CustomerSalesGroupCountTableConnection
        )

    @staticmethod
    def resolve_filter_material_code_name_customer_order(self, info, **kwargs):
        channel_type = kwargs.get("distributionChannelType", None)
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            resolve_distribution_channel_codes(channel_type))
        qs = resolve_filter_material_code_name_customer_order(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, CustomerMaterialCodeNameCountTableConnection)

    @staticmethod
    def resolve_customer_orders(self, info, **kwargs):
        created_by = info.context.user
        qs = resolve_customer_orders(created_by)
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(qs, info, kwargs, CustomerOrderCountTableConnection)

    @staticmethod
    def resolve_customer_order_confirmation(self, info, **kwargs):
        qs = resolve_customer_order_confirmation()
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, CustomerOrderCountTableConnection)

    @staticmethod
    def resolve_customer_orders_from_sap(self, info, **kwargs):
        data_input = kwargs.get("input", None)
        if data_input and data_input.get('create_date_from', None) and data_input.get('create_date_to', None):
            validate_date(data_input.get('create_date_from'), data_input.get('create_date_to'))
        return resolve_customer_orders_from_sap(info, data_input)


class CustomerCartQueries(graphene.ObjectType):
    customer_cart = PermissionsField(
        CustomerCart,
        description="Look up a customer cart by ID",
        id=graphene.Argument(
            graphene.ID,
            description="ID of a customer cart",
            required=True
        ),
    )

    customer_cart_product_variant = PermissionsField(
        CustomerCartProductVariant,
        description="Look up a customer cart by ID",
        id=graphene.Argument(
            graphene.ID,
            description="ID of a customer cart",
            required=True
        ),
    )

    customer_carts = FilterConnectionField(
        CustomerCartCountableConnection,
        description="Customer cart details",
        sold_to_id=graphene.Argument(
            graphene.ID, description="ID of an sold to", required=True
        ),
        sort_by=CustomerCartsSortingInput()
    )

    customer_cart_totals = PermissionsField(
        CustomerCartTotals,
        sold_to_id=graphene.Argument(
            graphene.ID, description="ID of an sold to", required=True
        ),
        description="return total contracts and total products in customer cart"
    )

    @staticmethod
    def resolve_customer_cart(self, info, **kwargs):
        id = kwargs.get('id')
        return resolve_customer_cart(id, info)
    
    @staticmethod
    def resolve_customer_cart_product_variant(self, info, **kwargs):
        id = kwargs.get('id')
        return resolve_customer_cart(id, info)

    @login_required
    def resolve_customer_carts(self, info, **kwargs):
        sold_to_id = kwargs.get("sold_to_id")
        qs = resolve_customer_carts(info.context.user, sold_to_id)
        return create_connection_slice(qs, info, kwargs, CustomerCartCountableConnection)

    @login_required
    def resolve_customer_cart_totals(self, info, **kwargs):
        sold_to_id = kwargs.get("sold_to_id")
        return resolve_customer_cart_totals(info.context.user, sold_to_id)


class CustomerContractQueries(graphene.ObjectType):
    scgp_customer_contracts = FilterConnectionField(
        CustomerContractCountableConnection,
        description="look up customer contracts by customer ID",
        contract_no=graphene.Argument(
            graphene.List(graphene.String), description="Number of contract"
        ),
        sold_to_id=graphene.Argument(
            graphene.ID, description="ID of an sold to", required=True
        ),
        filter=CustomerContractFilterInput(),
        sort_by=CustomerContractsSortingInput(),
    )

    customer_checkout_contract = graphene.Field(
        CustomerContract,
        description="look up scgp_customer contract by ID ",
        id=graphene.Argument(
            graphene.ID,
            required=True,
            description="ID of the contract"),
    )

    customer_contract_detail = graphene.Field(
        CustomerContract,
        description="look up scgp_customer contract by ID",
        id=graphene.Argument(
            graphene.ID,
            required=True,
            description="ID of the contract"),
    )

    scgp_customer_contract = graphene.Field(
        CustomerContract,
        description="look up scgp_customer contract by ID",
        id=graphene.Argument(
            graphene.ID,
            required=True,
            description="ID of the contract"),
    )

    @staticmethod
    def resolve_scgp_customer_contract(self, info, **kwargs):
        contract_id = kwargs.get("id")
        list_id = sync_contract_material(contract_id)
        info.variable_values.update({"list_contract_item": list_id})
        return resolve_contract(info, int(contract_id))

    @staticmethod
    def resolve_customer_contract_detail(self, info, **kwargs):
        contract_id = kwargs.get("id")
        return resolve_contract(info, contract_id)

    @staticmethod
    def resolve_customer_checkout_contract(self, info, **kwargs):
        contract_id = kwargs.get("id")
        return resolve_contract(info, contract_id)

    @staticmethod
    def resolve_scgp_customer_contracts(self, info, **kwargs):
        if kwargs.get("contract_no"):
            # type of contract_no is list
            for idx, contract_no in enumerate(kwargs["contract_no"]):
                kwargs["contract_no"][idx] = str(contract_no).zfill(10)
        result = call_sap_api_get_customer_contracts(info, kwargs)
        if not result:
            return CustomerContractCountableConnection(
                edges=[],
                page_info={
                    "has_next_page": False,
                    "has_previous_page": False,
                    "start_cursor": None,
                    "end_cursor": None,
                },
            )
        qs = resolve_scgp_customer_contracts(info, kwargs.get("contract_no"), kwargs.get("sold_to_id"), kwargs)
        kwargs.pop("sap_code")
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, CustomerContractCountableConnection
        )


class CustomerOrderMutations(graphene.ObjectType):
    update_customer_order = CustomerOrderUpdate.Field()
    create_customer_order = CreateCustomerOrder.Field()
    update_customer_order_lines = CustomerOrderLinesUpdate.Field()
    delete_customer_order_lines = CustomerOrderLinesDelete.Field()
    add_product_to_customer_order = CustomerOrderAddProduct.Field()
    update_request_date_on_iplan = UpdateRequestDateOnIplan.Field()


class CustomerCartMutations(graphene.ObjectType):
    delete_customer_cart_items = CartItemsDelete.Field()
    create_customer_cart = CustomerCartCreate.Field()
    update_customer_cart = CustomerCartUpdate.Field()
    update_customer_cart_lines = CustomerCartLinesUpdateQuantity.Field()


class CustomerContractProductQueries(graphene.ObjectType):
    customer_contract_product = graphene.Field(
        CustomerContractProduct,
        description="look up scgp_contract_product",
        contract_id=graphene.Argument(graphene.ID, required=True),
        product_id=graphene.Argument(graphene.ID, required=True),
        contract_material_id=graphene.Argument(graphene.ID, required=True)
    )

    @staticmethod
    def resolve_customer_contract_product(self, info, **kwargs):
        product_id = kwargs.get("product_id")
        contract_id = kwargs.get("contract_id")
        contract_material_id = kwargs.get("contract_material_id")
        list_standard_variants, list_non_standard_variants = sync_contract_material_variant(
            info.context.plugins.call_api_sap_client, product_id, contract_id)
        info.variable_values.update({"list_standard_variants": list_standard_variants})
        info.variable_values.update({"list_non_standard_variants": list_non_standard_variants})
        return resolve_contract_product(info, contract_material_id)


class CustomerExternalQueries(graphene.ObjectType):
    contract_unloading_point = graphene.List(
        CustomerUnloadingPoint,
        sold_to_code=graphene.Argument(graphene.String, required=True)
    )

    @staticmethod
    def resolve_contract_unloading_point(self, info, **kwargs):
        sold_to_code = kwargs.get("sold_to_code")
        return resolve_unloading_point(sold_to_code=sold_to_code)

    customer_lms_report = graphene.List(
        LmsReportCustomer,
        filter=graphene.Argument(CustomerLmsReportInput)

    )

    @staticmethod
    def resolve_customer_lms_report(root, info, **kwargs):
        input_from_user = kwargs.get("filter")

        return resolve_customer_lms_report(input_from_user, info)
