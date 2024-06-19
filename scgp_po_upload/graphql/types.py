
from saleor.graphql.core.types import ModelObjectType
from sap_migration.graphql.types import SoldToMaster
from scgp_export.graphql.types import ScgCountableConnection
from saleor.graphql.account.types import User
import graphene
import scgp_po_upload.models as models


class POUploadFileLog(ModelObjectType):
    id = graphene.ID()
    file_name = graphene.String()
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    file = graphene.String()
    uploaded_by = graphene.Field(User)
    status = graphene.String()
    note = graphene.String()

    class Meta:
        model = models.PoUploadFileLog


class POUploadFileLogCountableConnection(ScgCountableConnection):
    class Meta:
        node = POUploadFileLog



class PoUploadCustomerSettings(ModelObjectType):
    id = graphene.ID()
    sold_to = graphene.Field(SoldToMaster)
    use_customer_master = graphene.Boolean()
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    updated_by = graphene.Field(User)

    class Meta:
        model = models.PoUploadCustomerSettings


class PoUploadCustomerSettingsCountableConnection(ScgCountableConnection):
    class Meta:
        node = PoUploadCustomerSettings

