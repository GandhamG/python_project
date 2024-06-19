import graphene

from sap_migration.graphql.types import SoldToMasterCountableConnection
from scgp_po_upload.graphql.mutations.po_upload import (
    ScgpPoUploadSendMail,
    PoUploadFileMutation,
    PoUploadRetryUploadFile
)
from .filters import SoldToMasterFilterInput
from .mutations.excel_upload import ExcelUploadFileMutation, CheckExcelFileNameInvalid
from .mutations.master_mapping import (
    PoUploadCustomerSettingsCreate,
    PoUploadCustomerSettingsUpdate,
    PoUploadCustomerSettingsDelete
)
from .types import (
    POUploadFileLogCountableConnection,
    PoUploadCustomerSettingsCountableConnection,
)
from .sorters import POUploadFileLogSorterInput
from .resolvers.po_upload import (
    resolve_fail_files,
    resolve_po_upload_customer_settings, get_all_record_sold_to_master
)
from saleor.graphql.core.fields import (
    FilterConnectionField,
    ConnectionField
)
from saleor.graphql.core.connection import (
    filter_connection_queryset, create_connection_slice
)

from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from ..implementations.excel_upload_validation import validate_file_name, is_valid_excel_file


class ExcelUploadFile:
    pass


class ScgpPoUploadMutations(graphene.ObjectType):
    scgp_po_upload_send_mail = ScgpPoUploadSendMail.Field()
    upload_po = PoUploadFileMutation.Field()
    upload_Excel = ExcelUploadFileMutation.Field()
    retry_upload = PoUploadRetryUploadFile.Field()
    valid_excel_file = CheckExcelFileNameInvalid.Field()


class ScgpPoUploadQueries(graphene.ObjectType):
    failed_files = FilterConnectionField(
        POUploadFileLogCountableConnection,
        sort_by=POUploadFileLogSorterInput(),
        description="List of failed po upload file.",
    )

    @staticmethod
    def resolve_failed_files(self, info, **kwargs):
        qs = resolve_fail_files()
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(
            qs, info, kwargs, POUploadFileLogCountableConnection
        )


class ScgpPoUploadMasterMappingQueries(graphene.ObjectType):
    po_upload_customer_settings = ConnectionField(
        PoUploadCustomerSettingsCountableConnection,
        description="List of po upload customer settings"
    )

    po_upload_suggestion_search_sold_to = FilterConnectionField(
        SoldToMasterCountableConnection,
        filter=SoldToMasterFilterInput()
    )

    @staticmethod
    def resolve_po_upload_customer_settings(self, info, **kwargs):
        qs = resolve_po_upload_customer_settings()
        return create_connection_slice(
            qs, info, kwargs, PoUploadCustomerSettingsCountableConnection
        )

    @staticmethod
    def resolve_po_upload_suggestion_search_sold_to(self, info, **kwargs):
        qs = get_all_record_sold_to_master()
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(
            qs, info, kwargs, SoldToMasterCountableConnection
        )


class ScgpPoUploadMasterMappingMutations(graphene.ObjectType):
    po_upload_customer_settings_create = PoUploadCustomerSettingsCreate.Field()
    po_upload_customer_settings_update = PoUploadCustomerSettingsUpdate.Field()
    po_upload_customer_settings_delete = PoUploadCustomerSettingsDelete.Field()
