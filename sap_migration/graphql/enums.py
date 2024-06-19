import graphene
from sap_migration import error_codes as sap_migration_error_codes

SapMigrationErrorCode = graphene.Enum.from_enum(
    sap_migration_error_codes.SapMigration
)


class OrderType(graphene.Enum):
    DOMESTIC = "domestic"
    CUSTOMER = "customer"
    EXPORT = "export"
    EO = "eo"
    PO = "po"


class InquiryMethodType(graphene.Enum):
    DOMESTIC = "Domestic"
    CUSTOMER = "Customer"
    EXPORT = "Export"
    ASAP = "ASAP"


class CreatedFlow(graphene.Enum):
    DOMESTIC_EORDERING = "domestic_eordering"
    EXCEL_UPLOAD = "excel_upload"
