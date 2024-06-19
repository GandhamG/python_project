import graphene

from saleor.graphql.core.mutations import ModelMutation
from scgp_po_upload import models
from scgp_po_upload.graphql.implementations.master_mapping import (
    create_po_upload_customer_settings,
    delete_po_upload_customer_settings,
    update_po_upload_customer_settings,
)
from scgp_po_upload.graphql.po_upload_error import ScgpPoUploadError
from scgp_po_upload.graphql.types import PoUploadCustomerSettings


class PoUploadCustomerSettingsCreate(ModelMutation):
    class Arguments:
        sold_to_id = graphene.ID("SoldTo id want to create")

    class Meta:
        description = "Create PoUploadCustomerSettings"
        model = models.PoUploadCustomerSettings
        object_type = PoUploadCustomerSettings
        return_field_name = "cart"
        error_type_class = ScgpPoUploadError
        error_type_field = "upload_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        if user.is_anonymous:
            raise ValueError("You need to login")
        result = create_po_upload_customer_settings(user, data["sold_to_id"])
        return cls.success_response(result)


class PoUploadCustomerSettingsUpdate(ModelMutation):
    class Arguments:
        sold_to_id = graphene.ID(description="Sold to id want to update")
        use_customer_master = graphene.Boolean(description="True or False")

    class Meta:
        description = "Create PoUploadCustomerSettings"
        model = models.PoUploadCustomerSettings
        object_type = PoUploadCustomerSettings
        return_field_name = "cart"
        error_type_class = ScgpPoUploadError
        error_type_field = "upload_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        if user.is_anonymous:
            raise ValueError("You need to login")
        result = update_po_upload_customer_settings(
            user, data["sold_to_id"], data["use_customer_master"]
        )
        return cls.success_response(result)


class PoUploadCustomerSettingsDelete(ModelMutation):
    class Arguments:
        sold_to_id = graphene.ID(description="SoldTo id want to delete")

    class Meta:
        description = "Create PoUploadCustomerSettings"
        model = models.PoUploadCustomerSettings
        object_type = graphene.Boolean
        return_field_name = "cart"
        error_type_class = ScgpPoUploadError
        error_type_field = "upload_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        if user.is_anonymous:
            raise ValueError("You need to login")
        result = delete_po_upload_customer_settings(data["sold_to_id"])
        return cls.success_response(result)
