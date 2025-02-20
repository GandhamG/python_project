from typing import List

import graphene

from ...attribute import models as attribute_models
from ...core.permissions import PagePermissions
from ...page import models
from ..attribute.filters import AttributeFilterInput
from ..attribute.types import Attribute, AttributeCountableConnection, SelectedAttribute
from ..core.connection import (
    CountableConnection,
    create_connection_slice,
    filter_connection_queryset,
)
from ..core.descriptions import ADDED_IN_33, DEPRECATED_IN_3X_FIELD
from ..core.federation import federated_entity, resolve_federation_references
from ..core.fields import FilterConnectionField, JSONString, PermissionsField
from ..core.types import ModelObjectType, NonNullList
from ..meta.types import ObjectWithMetadata
from ..translations.fields import TranslationField
from ..translations.types import PageTranslation
from .dataloaders import (
    PageAttributesByPageTypeIdLoader,
    PagesByPageTypeIdLoader,
    PageTypeByIdLoader,
    SelectedAttributesByPageIdLoader,
)


@federated_entity("id")
class PageType(ModelObjectType):
    id = graphene.GlobalID(required=True)
    name = graphene.String(required=True)
    slug = graphene.String(required=True)
    attributes = NonNullList(
        Attribute, description="Page attributes of that page type."
    )
    available_attributes = FilterConnectionField(
        AttributeCountableConnection,
        filter=AttributeFilterInput(),
        description="Attributes that can be assigned to the page type.",
        permissions=[
            PagePermissions.MANAGE_PAGES,
        ],
    )
    has_pages = PermissionsField(
        graphene.Boolean,
        description="Whether page type has pages assigned.",
        permissions=[
            PagePermissions.MANAGE_PAGES,
        ],
    )

    class Meta:
        description = (
            "Represents a type of page. It defines what attributes are available to "
            "pages of this type."
        )
        interfaces = [graphene.relay.Node, ObjectWithMetadata]
        model = models.PageType

    @staticmethod
    def get_model():
        return models.PageType

    @staticmethod
    def resolve_attributes(root: models.PageType, info):
        return PageAttributesByPageTypeIdLoader(info.context).load(root.pk)

    @staticmethod
    def resolve_available_attributes(root: models.PageType, info, **kwargs):
        qs = attribute_models.Attribute.objects.get_unassigned_page_type_attributes(
            root.pk
        )
        qs = filter_connection_queryset(qs, kwargs, info.context)
        return create_connection_slice(qs, info, kwargs, AttributeCountableConnection)

    @staticmethod
    def resolve_has_pages(root: models.PageType, info, **kwargs):
        return (
            PagesByPageTypeIdLoader(info.context)
            .load(root.pk)
            .then(lambda pages: bool(pages))
        )

    @staticmethod
    def __resolve_references(roots: List["PageType"], info, **_kwargs):
        return resolve_federation_references(PageType, roots, models.PageType.objects)


class PageTypeCountableConnection(CountableConnection):
    class Meta:
        node = PageType


class Page(ModelObjectType):
    id = graphene.GlobalID(required=True)
    seo_title = graphene.String()
    seo_description = graphene.String()
    title = graphene.String(required=True)
    content = JSONString(description="Content of the page (JSON).")
    publication_date = graphene.Date(
        deprecation_reason=(
            f"{DEPRECATED_IN_3X_FIELD} "
            "Use the `publishedAt` field to fetch the publication date."
        ),
    )
    published_at = graphene.DateTime(
        description=f"{ADDED_IN_33} The page publication date."
    )
    is_published = graphene.Boolean(required=True)
    slug = graphene.String(required=True)
    page_type = graphene.Field(PageType, required=True)
    created = graphene.DateTime(required=True)
    content_json = JSONString(
        description="Content of the page (JSON).",
        deprecation_reason=f"{DEPRECATED_IN_3X_FIELD} Use the `content` field instead.",
        required=True,
    )
    translation = TranslationField(PageTranslation, type_name="page")
    attributes = NonNullList(
        SelectedAttribute,
        required=True,
        description="List of attributes assigned to this product.",
    )

    class Meta:
        description = (
            "A static page that can be manually added by a shop operator through the "
            "dashboard."
        )
        interfaces = [graphene.relay.Node, ObjectWithMetadata]
        model = models.Page

    @staticmethod
    def resolve_publication_date(root: models.Page, info, **_kwargs):
        return root.published_at

    @staticmethod
    def resolve_created(root: models.Page, _info):
        return root.created_at

    @staticmethod
    def resolve_page_type(root: models.Page, info):
        return PageTypeByIdLoader(info.context).load(root.page_type_id)

    @staticmethod
    def resolve_content_json(root: models.Page, info):
        content = root.content
        return content if content is not None else {}

    @staticmethod
    def resolve_attributes(root: models.Page, info):
        return SelectedAttributesByPageIdLoader(info.context).load(root.id)


class PageCountableConnection(CountableConnection):
    class Meta:
        node = Page
