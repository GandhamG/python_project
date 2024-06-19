import graphene
from django.core.exceptions import ValidationError

from saleor.core.permissions import AuthorizationFilters
from saleor.graphql.core.mutations import ModelMutation, ModelDeleteMutation, BaseMutation
from saleor.graphql.core.types import NonNullList, File
from scg_checkout import models
from sap_migration import models as migration_models
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scg_checkout.graphql.enums import AlternativeMaterial as AlternativeMaterialEnum, AlternativeMaterialInputFields
from scg_checkout.graphql.helper import alt_mat_mapping_duplicate_validation
from scg_checkout.graphql.implementations.materials import export_alternative_material_excel_file, \
    export_alternative_material_log_excel_file
from scg_checkout.graphql.resolves.alternative_material import (
    map_request_fields_by_type,
    alternative_material_add, delete_alternative_material_os, edit_alternative_material,
    EDIT_ALT_MAT_MAPPING_NOT_FOUND,
)
from scg_checkout.graphql.types import AlternativeMaterial, AlternativeMaterialOs


class AlternativeMaterialOsDelete(ModelDeleteMutation):
    status = graphene.String()

    class Meta:
        description = "Delete alternate material."
        model = migration_models.AlternateMaterialOs
        object_type = AlternativeMaterialOs
        return_field_name = "alternate_material_os"
        error_type_class = ContractCheckoutError
        error_type_field = "material_errors"

    class Arguments:
        alternative_material_os_id = graphene.ID(
            description="ID of alternate material os to delete", required=True
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        alternative_material_os_id = data["alternative_material_os_id"]
        delete_alternative_material_os(alternative_material_os_id, info.context.user)

        return cls(status=True)


class AlternativeMaterialItemInput(graphene.InputObjectType):
    priority = graphene.Int(required=True, description="Priority of the Alternative Material.")
    material_os_id = graphene.ID(description="ID of the Material Os.")
    dia = graphene.String(description="Diameter of the Material Os.")


class AlternativeMaterialAddInput(graphene.InputObjectType):
    sale_organization_id = graphene.ID(required=True, description="ID of the Sale Organization.")
    sold_to_id = graphene.ID(required=True, description="ID of the sold to.")
    type = graphene.String(required=True, description="Type of the Alternative Material.")
    material_own_id = graphene.ID(description="ID of the Material Own.")
    lines = NonNullList(
        AlternativeMaterialItemInput,
        description=(
            "A list of Material Os, each containing information about "
            "an Alternative Material."
        ),
        required=True,
    )


class AlternativeMaterialAdd(ModelMutation):
    class Arguments:
        input = AlternativeMaterialAddInput(required=True, description="Fields required to add alternative material.")

    class Meta:
        description = "Add alternative material"
        model = migration_models.AlternateMaterial
        object_type = AlternativeMaterial
        return_field_name = "alternativeMaterials"
        error_type_class = ContractCheckoutError
        error_type_field = "material_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def clean_input(cls, root, info, data):
        types = data["type"]
        require_fields = AlternativeMaterialInputFields.FIELDS.value
        request_fields = map_request_fields_by_type(data, require_fields)
        sale_organization_id = request_fields.get("sale_organization_id", False)
        sold_to_id = request_fields.get("sold_to_id", False)
        material_own_id = request_fields.get("material_own_id", False)
        lines = request_fields.get("lines", False)
        alt_mat_mapping_duplicate_validation(material_own_id, sale_organization_id, sold_to_id)

        dia_errors = {}
        if types == "Grade/Gram":
            for line in lines:
                priority = line.get("priority")
                dia = line.get("dia", "").strip()
                if len(dia) > AlternativeMaterialEnum.DIA_LENGTH.value or not dia.isnumeric():
                    dia_errors[priority] = ValidationError(
                        f"โปรดระบุ Dia เป็นตัวเลข",
                        code=ContractCheckoutErrorCode.INVALID.value,
                    )

        if dia_errors:
            raise ValidationError(dia_errors)

        input_data = {
            "type": types,
            **request_fields,
        }
        return input_data

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data = data["input"]
        user = info.context.user
        cls.clean_input(root, info, data)
        result = alternative_material_add(data, user)
        return cls.success_response(result)


class AlternativeMaterialEditInput(graphene.InputObjectType):
    sale_organization_id = graphene.ID(required=True, description="ID of the Sale Organization.")
    sold_to_id = graphene.ID(required=True, description="ID of the sold to.")
    material_own_id = graphene.ID(description="ID of the Material Own.")
    lines = NonNullList(
        AlternativeMaterialItemInput,
        description=(
            "A list of alternative material os items, each containing information about "
            "an item in the Alternative Material."
        ),
        required=True,
    )


class AlternativeMaterialEdit(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a alternative material to edit.", required=True)
        input = AlternativeMaterialEditInput(
            required=True,
            description="Fields required to edit alternative material.")

    class Meta:
        description = "Edit alternative material"
        model = migration_models.AlternateMaterial
        object_type = AlternativeMaterial
        return_field_name = "alternativeMaterial"
        error_type_class = ContractCheckoutError
        error_type_field = "material_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def clean_input(cls, info, data):
        alternative_material_id = data.get("id")
        alternative_material = migration_models.AlternateMaterial.objects.filter(id=alternative_material_id).first()
        if not alternative_material:
            raise ValidationError(
                {
                    "alternative_material_id": ValidationError(
                        EDIT_ALT_MAT_MAPPING_NOT_FOUND,
                        code=ContractCheckoutErrorCode.INVALID.value,
                    )
                }
            )

        data = data["input"]
        require_fields = AlternativeMaterialInputFields.FIELDS.value
        request_fields = map_request_fields_by_type(data, require_fields)
        sale_organization_id = request_fields.get("sale_organization_id", False)
        sold_to_id = request_fields.get("sold_to_id", False)
        material_own_id = request_fields.get("material_own_id", False)
        lines = request_fields.get("lines", False)

        alt_mat_mapping_duplicate_validation(material_own_id, sale_organization_id, sold_to_id, alternative_material)

        alternative_type = alternative_material.type
        dia_errors = {}
        if alternative_type == "":
            for line in lines:
                priority = line.get("priority")
                dia = line.get("dia", "").strip()
                if len(dia) > AlternativeMaterialEnum.DIA_LENGTH.value or not dia.isnumeric():
                    dia_errors[priority] = ValidationError(
                        f"โปรดระบุ Dia เป็นตัวเลข",
                        code=ContractCheckoutErrorCode.INVALID.value,
                    )

        if dia_errors:
            raise ValidationError(dia_errors)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        cls.clean_input(info, data)
        result = edit_alternative_material(data["id"], data["input"], info.context.user)
        return cls.success_response(result)


class AlternativeMaterialExport(BaseMutation):
    file_name = graphene.String()
    content_type = graphene.String()
    exported_file_base_64 = graphene.String()

    class Meta:
        description = "export alternated materials and return link to download"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        file_name, content_type, base64_string = export_alternative_material_excel_file()
        return AlternativeMaterialExport(
            file_name=file_name,
            content_type=content_type,
            exported_file_base_64=base64_string
        )


class AlternativeMaterialLogExport(BaseMutation):
    file_name = graphene.String()
    content_type = graphene.String()
    exported_file_base_64 = graphene.String()

    class Meta:
        description = "export alternated material log and return link to download"
        error_type_class = ContractCheckoutError

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        file_name, content_type, base64_string = export_alternative_material_log_excel_file()
        return AlternativeMaterialLogExport(
            file_name=file_name,
            content_type=content_type,
            exported_file_base_64=base64_string
        )
