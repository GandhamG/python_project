import graphene

from saleor.graphql.core.connection import (
    filter_connection_queryset,
    create_connection_slice,
)
from saleor.graphql.core.fields import (
    FilterConnectionField,
)
from sap_master_data.graphql.types import (
    RequireAttentionFlag,
    MaterialSaleMaster, SourceOfApp
)
from sap_migration.graphql.types import MaterialVariantMasterCountTableConnection, MaterialMasterCountTableConnection
from scg_checkout.graphql.enums import DistributionChannelType
from scg_checkout.graphql.filters import SuggestionSearchUserByNameFilterInput

from scg_checkout.graphql.resolves.checkouts import resolve_suggestion_search_user_by_name
from scg_checkout.graphql.resolves.order_organization import resolve_distribution_channel_codes


from scg_checkout.graphql.types import (
    SalesOrganization,
    SalesGroup,
    BusinessUnit,
    ScgpMaterialGroup,
)
from scgp_export.graphql.resolvers.connections import (
    resolve_connection_slice,
    resolve_connection_slice_for_overdue
)
from scgp_export.graphql.types import ExportOrder, StockOnHandReport
from scgp_require_attention_items.graphql.enums import ScgpRequireAttentionTypeData, SourceOfAppData
from scgp_require_attention_items.graphql.filters import (
    RequireAttentionSalesOrganizationFilterInput,
    RequireAttentionSalesGroupFilterInput,
    RequireAttentionSoldToFilterInput,
    RequireAttentionShipToFilterInput,
    RequireAttentionMaterialFilterInput,
    RequireAttentionPlantFilterInput,
    RequireAttentionSaleEmployeeFilterInput,
    RequireAttentionItemsFilterInput,
    RequireAttentionMaterialGradeGramFilterInput,
    SalesOrderFilterInput,
    SuggestionSearchMaterialGradeGramFilterInput,
    ReportOrderPendingSoldToFilterInput,
)

from scgp_require_attention_items.graphql.mutations.scgp_require_attention_items import (
    RequireAttentionItemsUpdateParameter,
    ChangeParameterIPlan,
    PassParameterToIPlan,
    EditRequireAttentionItems,
    AcceptConfirmDateRequireAttentionItems,
)

from scgp_require_attention_items.graphql.mutations.scgp_require_attention_items import (
    RequireAttentionItemsDelete,
    AcceptConfirmDate,
)
from scgp_require_attention_items.graphql.resolvers.Stock_on_hand_report import resolve_get_stock_on_hand_report
from scgp_require_attention_items.graphql.resolvers.require_attention_items import (
    resolve_filter_require_attention_sales_organization,
    resolve_filter_require_attention_business_unit,
    resolve_filter_require_attention_sales_group,
    resolve_require_attention_item_status,
    resolve_require_attention_type,
    resolve_filter_require_attention_material,
    resolve_filter_require_attention_material_group,
    resolve_filter_require_attention_sold_to,
    resolve_filter_require_attention_sale_employee,
    resolve_filter_require_attention_view_all,
    resolve_require_attention_inquiry_method_code,
    resolve_require_attention_type_of_delivery,
    resolve_require_attention_split_order_item_partial_delivery,
    resolve_require_attention_consignment,
    resolve_filter_require_attention_view_by_ids,
    resolve_filter_require_attention_view_by_role,
    resolve_filter_require_attention_material_variant_master,
    resolve_order_lines_all,
    resolve_material_sale_master_distinct_on_material_group_1,
    resolve_material_pricing_group_distinct,
    resolve_list_order_type_distinct,
    resolve_all_suggestion_search_for_material_grade_gram,
    list_empty_sold_to_master,
    resolve_suggestion_search_sold_to_report_order_pending,
    resolve_suggestion_search_sales_organization_report_order_pending,
    resolve_suggestion_search_material_no_grade_gram_report_order_pending,
    resolve_suggestion_search_ship_to_report_order_pending_data,
    resolve_filter_require_attention_edit_items_by_ids,
    resolve_list_of_sale_order_sap_order_pending,
    resolve_list_of_sale_order_and_excel,
    resolve_filter_require_attention_material_master, resolve_material_sale_master_distinct_on_distribution_channel,
    resolve_download_list_of_sale_order_excel,
)
from scgp_require_attention_items.graphql.sorters import RequireAttentionItemsSortingInput
from scgp_require_attention_items.graphql.types import (
    RequireAttentionSalesOrganizationCountTableConnection,
    RequireAttentionSalesGroupCountTableConnection,
    RequireAttentionEnums,
    RequireAttentionSoldToCountTableConnection,
    RequireAttentionPlantCountTableConnection,
    RequireAttentionSaleEmployeeCountTableConnection,
    RequireAttentionItemsCountTableConnection,
    RequireAttentionMaterialGradeGramCountTableConnection,
    RequireAttentionItemsViewCountTableConnection,
    ReportListOfSalesOrderCountableConnection,
    RequireAttentionItems,
    ReportOrderPendingSoldToCountTableConnection,
    ReportOrderPendingShipToItems,
    CreateByCountableConnection,
    SAPListOfSaleOrder,
    SAPListOfSaleOrderInput,
    SAPListOfSaleOrderPendingInput,
    SAPListOfSaleOrderPending,
    SAPListOfSaleOrderAndExcel,
)
from scgp_require_attention_items.graphql.validators import (
    validate_overdue_1,
    validate_overdue_2
)


class RequireAttentionItemsQueries(graphene.ObjectType):
    filter_require_attention_sold_to = FilterConnectionField(
        RequireAttentionSoldToCountTableConnection,
        filter=RequireAttentionSoldToFilterInput()
    )

    filter_require_attention_ship_to = FilterConnectionField(
        RequireAttentionItemsCountTableConnection,
        filter=RequireAttentionShipToFilterInput()
    )

    filter_require_attention_sale_employee = FilterConnectionField(
        RequireAttentionSaleEmployeeCountTableConnection,
        filter=RequireAttentionSaleEmployeeFilterInput()
    )

    filter_require_attention_material_group = graphene.List(ScgpMaterialGroup)

    filter_require_attention_sales_organization = graphene.List(SalesOrganization)

    filter_require_attention_business_unit = graphene.List(BusinessUnit)

    filter_require_attention_sales_group = graphene.List(SalesGroup)

    filter_require_attention_sales_organization_by_bu = FilterConnectionField(
        RequireAttentionSalesOrganizationCountTableConnection,
        filter=RequireAttentionSalesOrganizationFilterInput()
    )

    filter_require_attention_sales_group_by_sales_organization = FilterConnectionField(
        RequireAttentionSalesGroupCountTableConnection,
        filter=RequireAttentionSalesGroupFilterInput()
    )

    filter_require_attention_material = FilterConnectionField(
        MaterialMasterCountTableConnection,
        distributionChannelType=graphene.Argument(DistributionChannelType, description="Distribution channel type",
                                                  required=True),
        filter=RequireAttentionMaterialFilterInput()
    )

    filter_require_attention_material_grade_gram = FilterConnectionField(
        RequireAttentionMaterialGradeGramCountTableConnection,
        filter=RequireAttentionMaterialGradeGramFilterInput()
    )

    require_attention_item_status = graphene.List(RequireAttentionEnums)

    require_attention_type = graphene.List(RequireAttentionEnums)

    require_attention_inquiry_method_code = graphene.List(RequireAttentionEnums)

    require_attention_type_of_delivery = graphene.List(RequireAttentionEnums)

    require_attention_split_order_item_partial_delivery = graphene.List(RequireAttentionEnums)

    require_attention_consignment = graphene.List(RequireAttentionEnums)

    require_attention_plant = FilterConnectionField(
        RequireAttentionPlantCountTableConnection,
        filter=RequireAttentionPlantFilterInput()
    )

    require_attention_items = FilterConnectionField(
        RequireAttentionItemsViewCountTableConnection,
        role=graphene.Argument(graphene.String, required=True),
        sort_by=RequireAttentionItemsSortingInput(description="Sort require attention items."),
        filter=RequireAttentionItemsFilterInput(description="Filtering options for require attention items."),
        description="List of require attention items.",
    )

    require_attention_items_by_ids = FilterConnectionField(
        RequireAttentionItemsViewCountTableConnection,
        sort_by=RequireAttentionItemsSortingInput(description="Sort require attention items."),
        ids=graphene.Argument(
            graphene.List(graphene.ID), description="ID of an scgp_require_attention_items"
        ),
        description="Look up scgp_require_attention_items by IDs",
    )

    require_attention_edit_items_by_ids = FilterConnectionField(
        RequireAttentionItemsViewCountTableConnection,
        sort_by=RequireAttentionItemsSortingInput(description="Sort require attention items."),
        ids=graphene.Argument(
            graphene.List(graphene.ID), description="ID of an scgp_require_attention_items"
        ),
        description="Look up scgp_require_attention_items by IDs",
    )

    suggestion_search_for_material_grade_gram = FilterConnectionField(
        MaterialVariantMasterCountTableConnection,
        filter=SuggestionSearchMaterialGradeGramFilterInput(
            description="Suggestion search for material grade grams"
        )
    )

    @staticmethod
    def resolve_require_attention_items(self, info, **kwargs):
        qs = resolve_filter_require_attention_view_by_role(kwargs.get('role'))
        qs = filter_connection_queryset(qs, kwargs)
        filters = kwargs.get("filter", None)
        request_date = filters.get("request_date", None)
        confirmed_date = filters.get("confirm_date", None)
        if request_date:
            validate_overdue_1(request_date)
        if confirmed_date:
            validate_overdue_2(confirmed_date)
        return resolve_connection_slice_for_overdue(
            qs, info, kwargs, RequireAttentionItemsCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_sold_to(self, info, **kwargs):
        qs = resolve_filter_require_attention_sold_to()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionSoldToCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_ship_to(self, info, **kwargs):
        qs = resolve_order_lines_all()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionItemsCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_sale_employee(self, info, **kwargs):
        qs = resolve_filter_require_attention_sale_employee()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionSaleEmployeeCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_material(self, info, **kwargs):
        channel_type = kwargs.get("distributionChannelType", None)
        qs = resolve_material_sale_master_distinct_on_distribution_channel(
            resolve_distribution_channel_codes(channel_type))
        qs = resolve_filter_require_attention_material_master(qs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, MaterialVariantMasterCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_material_group(self, info, **kwargs):
        return resolve_filter_require_attention_material_group()

    @staticmethod
    def resolve_filter_require_attention_sales_organization(self, info, **kwargs):
        return resolve_filter_require_attention_sales_organization()

    @staticmethod
    def resolve_filter_require_attention_business_unit(self, info, **kwargs):
        return resolve_filter_require_attention_business_unit()

    @staticmethod
    def resolve_filter_require_attention_sales_group(self, info, **kwargs):
        return resolve_filter_require_attention_sales_group()

    @staticmethod
    def resolve_filter_require_attention_sales_organization_by_bu(self, info, **kwargs):
        qs = resolve_filter_require_attention_sales_organization()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionSalesOrganizationCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_sales_group_by_sales_organization(self, info, **kwargs):
        qs = resolve_filter_require_attention_sales_group()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionSalesGroupCountTableConnection
        )

    @staticmethod
    def resolve_require_attention_plant(self, info, **kwargs):
        qs = resolve_filter_require_attention_view_all()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionPlantCountTableConnection
        )

    @staticmethod
    def resolve_require_attention_item_status(self, info):
        return resolve_require_attention_item_status()

    @staticmethod
    def resolve_require_attention_type(self, info):
        return resolve_require_attention_type()

    @staticmethod
    def resolve_require_attention_inquiry_method_code(self, info, **kwargs):
        return resolve_require_attention_inquiry_method_code()

    @staticmethod
    def resolve_require_attention_type_of_delivery(self, info, **kwargs):
        return resolve_require_attention_type_of_delivery()

    @staticmethod
    def resolve_require_attention_split_order_item_partial_delivery(self, info, **kwargs):
        return resolve_require_attention_split_order_item_partial_delivery()

    @staticmethod
    def resolve_require_attention_consignment(self, info, **kwargs):
        return resolve_require_attention_consignment()

    @staticmethod
    def resolve_require_attention_items_by_ids(self, info, ids, **kwargs):
        qs = resolve_filter_require_attention_view_by_ids(ids)
        return resolve_connection_slice(
            qs, info, kwargs, RequireAttentionItemsViewCountTableConnection
        )

    @staticmethod
    def resolve_require_attention_edit_items_by_ids(self, info, ids, **kwargs):
        qs = resolve_filter_require_attention_edit_items_by_ids(ids)
        return resolve_connection_slice_for_overdue(
            qs, info, kwargs, RequireAttentionItemsViewCountTableConnection
        )

    @staticmethod
    def resolve_filter_require_attention_material_grade_gram(self, info, **kwargs):
        qs = resolve_filter_require_attention_material()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, RequireAttentionMaterialGradeGramCountTableConnection
        )

    @staticmethod
    def resolve_suggestion_search_for_material_grade_gram(self, info, **kwargs):
        qs = resolve_all_suggestion_search_for_material_grade_gram()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, MaterialVariantMasterCountTableConnection
        )


class RequireAttentionItemsMutations(graphene.ObjectType):
    delete_require_attention_items = RequireAttentionItemsDelete.Field()
    update_require_attention_items_parameter = RequireAttentionItemsUpdateParameter.Field()
    accept_confirm_date = AcceptConfirmDate.Field()
    change_parameter_i_plan = ChangeParameterIPlan.Field()
    pass_parameter_to_i_plan = PassParameterToIPlan.Field()
    edit_require_attention_items = EditRequireAttentionItems.Field()
    accept_confirm_date_require_attention_items = AcceptConfirmDateRequireAttentionItems.Field()


class ScgpReportQueries(graphene.ObjectType):
    dropdown_list_material_group_1 = graphene.List(MaterialSaleMaster)

    report_list_of_sales_order = FilterConnectionField(
        ReportListOfSalesOrderCountableConnection,
        filter=SalesOrderFilterInput(),
        description="Search for sales order part"
    )

    report_list_of_sales_order_download = FilterConnectionField(
        ReportListOfSalesOrderCountableConnection,
        filter=SalesOrderFilterInput(),
        description="Search for sales order part"
    )

    download_report_sale_order = graphene.Field(
        graphene.String,
    )

    list_require_attention_flag = graphene.List(
        RequireAttentionFlag,
        description="List of drop down require attention flag"
    )
    list_source_of_app=graphene.List(
        SourceOfApp,
        description="List of drop down source of App "
    )

    drop_down_list_order_type = graphene.List(ExportOrder)

    drop_down_material_pricing_group = graphene.List(RequireAttentionItems)

    suggestion_search_create_by_sale_order = FilterConnectionField(
        CreateByCountableConnection,
        filter=SuggestionSearchUserByNameFilterInput(),
        description="Suggestion search for create by"
    )

    suggestion_search_material_grade_gram = FilterConnectionField(
        MaterialVariantMasterCountTableConnection,
        filter=SuggestionSearchMaterialGradeGramFilterInput(),
    )

    suggestion_search_sold_to_report_order_pending = FilterConnectionField(
        ReportOrderPendingSoldToCountTableConnection,
        filter=ReportOrderPendingSoldToFilterInput(),
        description="Search for sold to"
    )

    suggestion_search_sales_organization_report_order_pending = graphene.List(SalesOrganization)

    suggestion_search_ship_to_report_order_pending = graphene.List(
        ReportOrderPendingShipToItems,
        ship_to_search=graphene.String(),
        sold_to_code=graphene.List(graphene.String),
        description="Search for ship to",
    )

    suggestion_search_material_no_grade_gram_report_order_pending = FilterConnectionField(
        MaterialVariantMasterCountTableConnection,
        filter=SuggestionSearchMaterialGradeGramFilterInput(
            description="Suggestion search for material grade grams"
        ),
        material_grade_gram=graphene.Argument(graphene.String, description="material/grade-gram"),
    )
    list_of_sale_order_sap = graphene.List(
        SAPListOfSaleOrder,
        filter=graphene.Argument(SAPListOfSaleOrderInput)
    )

    list_of_sale_order_pending_sap = graphene.List(
        SAPListOfSaleOrderPending,
        filter=graphene.Argument(SAPListOfSaleOrderPendingInput)
    )

    list_of_sale_order_and_excel = graphene.Field(
        SAPListOfSaleOrderAndExcel,
        filter=graphene.Argument(SAPListOfSaleOrderInput)
    )

    download_list_of_sale_order_excel = graphene.Field(
        SAPListOfSaleOrderAndExcel,
        filter=graphene.Argument(SAPListOfSaleOrderInput)
    )

    @staticmethod
    def resolve_download_list_of_sale_order_excel(root, info, **kwargs):
        input_from_user = kwargs.get('filter')
        return resolve_download_list_of_sale_order_excel(input_from_user, info)

    @staticmethod
    def resolve_list_of_sale_order_and_excel(root, info, **kwargs):
        input_from_user = kwargs.get('filter')
        return resolve_list_of_sale_order_and_excel(input_from_user, info)

    @staticmethod
    def resolve_list_of_sale_order_sap(root, info, **kwargs):
        return

    @staticmethod
    def resolve_download_report_sale_order(root, info, **kwargs):
        return

    @staticmethod
    def resolve_dropdown_list_material_group_1(root, info, **kwargs):
        return resolve_material_sale_master_distinct_on_material_group_1()

    @staticmethod
    def resolve_report_list_of_sales_order(root, info, **kwargs):
        qs = resolve_order_lines_all()
        return resolve_connection_slice(
            qs, info, kwargs, ReportListOfSalesOrderCountableConnection)

    @staticmethod
    def resolve_report_list_of_sales_order_download(root, info, **kwargs):
        return resolve_connection_slice(
            list_empty_sold_to_master(), info, kwargs, ReportListOfSalesOrderCountableConnection)

    @staticmethod
    def resolve_list_require_attention_flag(root, info, **kwargs):
        list_enum = []
        for pair in ScgpRequireAttentionTypeData.__enum__:
            list_enum.append([pair.name, pair.value])
        return list_enum
    @staticmethod
    def resolve_list_source_of_app(root, info, **kwargs):
        list_enum = []
        for pair in SourceOfAppData.__enum__:
            list_enum.append([pair.name, pair.value])
        return list_enum
    @staticmethod
    def resolve_drop_down_material_pricing_group(root, info, **kwargs):
        return resolve_material_pricing_group_distinct()

    @staticmethod
    def resolve_drop_down_list_order_type(root, info, **kwargs):
        return resolve_list_order_type_distinct()

    @staticmethod
    def resolve_suggestion_search_create_by_sale_order(root, info, **kwargs):
        qs = resolve_suggestion_search_user_by_name()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, CreateByCountableConnection)

    @staticmethod
    def resolve_suggestion_search_sold_to_report_order_pending(root, info, **kwargs):
        qs = resolve_suggestion_search_sold_to_report_order_pending()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, CreateByCountableConnection)

    @staticmethod
    def resolve_suggestion_search_sales_organization_report_order_pending(root, info, **kwargs):
        return resolve_suggestion_search_sales_organization_report_order_pending()

    @staticmethod
    def resolve_suggestion_search_material_no_grade_gram_report_order_pending(root, info, **kwargs):
        qs = resolve_suggestion_search_material_no_grade_gram_report_order_pending(kwargs)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, MaterialVariantMasterCountTableConnection
        )

    @staticmethod
    def resolve_suggestion_search_ship_to_report_order_pending(self, info, **kwargs):
        data = resolve_suggestion_search_ship_to_report_order_pending_data(info, kwargs)
        if ship_to_search := kwargs.get("ship_to_search"):
            data = list(filter(lambda x: ship_to_search.lower() in x.get("name", "").lower(), data))
        return data

    @staticmethod
    def resolve_list_of_sale_order_pending_sap(root, info, **kwargs):
        input_from_user = kwargs.get('filter')
        return resolve_list_of_sale_order_sap_order_pending(input_from_user, info)


class GetOnHandReportInput(graphene.InputObjectType):
    code = graphene.String()
    unit = graphene.String()
    type = graphene.String()


class StockOnHandReportQueries(graphene.ObjectType):
    get_stock_on_hand_report = graphene.Field(
        StockOnHandReport,
        input=graphene.Argument(GetOnHandReportInput, required=True)
    )

    @staticmethod
    def resolve_get_stock_on_hand_report(root, info, **kwargs):
        return resolve_get_stock_on_hand_report(root, info, **kwargs)
