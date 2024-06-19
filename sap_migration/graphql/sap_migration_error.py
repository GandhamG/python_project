from saleor.graphql.core.types.common import Error
from .enums import SapMigrationErrorCode


class SapMigrationError(Error):
    code = SapMigrationErrorCode(description="The error code.", required=True)
