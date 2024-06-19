from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from common.graphql.schema import MulesoftAPILogMutations
from common.pmt.graphql.schema import PMTQueries
from scg_checkout.graphql.schema import (
    CheckoutBusinessUnitQueries,
    CheckoutContractProductQueries,
    CheckoutContractQueries,
    ContractCheckoutQueries,
    ContractCheckoutMutations,
    ContractOrderMutations,
    CustomerGroupMasterQueries,
    IncotermMasterQueries,
    OrganizationQueries,
    ContractOrderQueries,
    AlternativeMaterialMutations,
    RealtimePartnerMutations,
    ScgMaterialMutations,
    ScgMaterialQueries,
    AlternativeMaterialQueries,
    ScgSoldToQueries,
    DtpDtrMutations,
    ATPCTPQueries,
    RouteQueries,
    DeliveryReportQueries,
    CartItemsQueries,

    CheckoutATPCTPMutations, CustomerMaterialMutations, CustomerMaterialQueries,
)
from scg_cognito.graphql.schema import CognitoMutations
from scg_contract.graphql.schema import ContractQueries
from scg_customer.graphql.schema import CustomerQueries
from scgp_cip.graphql.order.schema import CIPOrderQueries, CIPOrderMutation
from scgp_cip.graphql.order_line.schema import CIPOrderLineQueries, CIPOrderLineMutation
from scgp_customer.graphql.schema import (
    CustomerExternalQueries,
    CustomerOrderQueries,
    CustomerCartQueries,
    CustomerOrderMutations,
    CustomerCartMutations,
    CustomerContractProductQueries,
    CustomerContractQueries,
)
from scgp_export.graphql.schema import (
    ExportOrderQueries,
    ExportSoldToQueries,
    ExportOrderMutations,
    ExportCartMutations,
    ExportPIQueries,
    ExportCartQueries,
    ATPCTPMutations,
    ExportATPCTPMutations,
)
from scgp_po_upload.graphql.schema import ScgpPoUploadMutations, ScgpPoUploadQueries, \
    ScgpPoUploadMasterMappingMutations, ScgpPoUploadMasterMappingQueries
from scgp_require_attention_items.graphql.schema import (
    RequireAttentionItemsQueries,
    RequireAttentionItemsMutations,
    ScgpReportQueries,
    StockOnHandReportQueries,
)
from scgp_user_management.graphql.schema import (
    ScgpUserManagementMutations,
    ScgpUserManagementQueries,
)
from .account.schema import AccountMutations, AccountQueries
from .app.schema import AppMutations, AppQueries
from .attribute.schema import AttributeMutations, AttributeQueries
from .channel.schema import ChannelMutations, ChannelQueries
from .checkout.schema import CheckoutMutations, CheckoutQueries
from .core.enums import unit_enums
from .core.federation.schema import build_federated_schema
from .core.schema import CoreMutations, CoreQueries
from .csv.schema import CsvMutations, CsvQueries
from .discount.schema import DiscountMutations, DiscountQueries
from .giftcard.schema import GiftCardMutations, GiftCardQueries
from .invoice.schema import InvoiceMutations
from .menu.schema import MenuMutations, MenuQueries
from .meta.schema import MetaMutations
from .order.schema import OrderMutations, OrderQueries
from .page.schema import PageMutations, PageQueries
from .payment.schema import PaymentMutations, PaymentQueries
from .plugins.schema import PluginsMutations, PluginsQueries
from .product.schema import ProductMutations, ProductQueries
from .shipping.schema import ShippingMutations, ShippingQueries
from .shop.schema import ShopMutations, ShopQueries
from .translations.schema import TranslationQueries
from .warehouse.schema import StockQueries, WarehouseMutations, WarehouseQueries
from .webhook.schema import WebhookMutations, WebhookQueries
from .webhook.subscription_types import Subscription
from ..graphql.notifications.schema import ExternalNotificationMutations

API_PATH = SimpleLazyObject(lambda: reverse("api"))


class Query(
    AccountQueries,
    AppQueries,
    AttributeQueries,
    ChannelQueries,
    CheckoutQueries,
    CoreQueries,
    CsvQueries,
    DiscountQueries,
    PluginsQueries,
    GiftCardQueries,
    MenuQueries,
    OrderQueries,
    PageQueries,
    PaymentQueries,
    ProductQueries,
    ShippingQueries,
    ShopQueries,
    StockQueries,
    TranslationQueries,
    WarehouseQueries,
    WebhookQueries,
    CustomerQueries,
    ContractQueries,
    CheckoutContractQueries,
    CheckoutBusinessUnitQueries,
    ContractCheckoutQueries,
    CheckoutContractProductQueries,
    OrganizationQueries,
    ContractOrderQueries,
    CustomerOrderQueries,
    CustomerContractQueries,
    CustomerCartQueries,
    CustomerContractProductQueries,
    ExportOrderQueries,
    ExportPIQueries,
    ExportSoldToQueries,
    ExportCartQueries,
    ScgpUserManagementQueries,
    RequireAttentionItemsQueries,
    ScgMaterialQueries,
    AlternativeMaterialQueries,
    ScgSoldToQueries,
    ScgpPoUploadQueries,
    ScgpPoUploadMasterMappingQueries,
    CustomerGroupMasterQueries,
    IncotermMasterQueries,
    ATPCTPQueries,
    ScgpReportQueries,
    RouteQueries,
    CustomerExternalQueries,
    DeliveryReportQueries,
    StockOnHandReportQueries,
    CartItemsQueries,
    CustomerMaterialQueries,
    CIPOrderQueries,
    PMTQueries,
    CIPOrderLineQueries,
):
    pass


class Mutation(
    AccountMutations,
    AppMutations,
    AttributeMutations,
    ChannelMutations,
    CheckoutMutations,
    CoreMutations,
    CsvMutations,
    DiscountMutations,
    ExternalNotificationMutations,
    PluginsMutations,
    GiftCardMutations,
    InvoiceMutations,
    MenuMutations,
    MetaMutations,
    OrderMutations,
    PageMutations,
    PaymentMutations,
    ProductMutations,
    ShippingMutations,
    ShopMutations,
    WarehouseMutations,
    WebhookMutations,
    CognitoMutations,
    ContractCheckoutMutations,
    ContractOrderMutations,
    CustomerOrderMutations,
    CustomerCartMutations,
    ExportOrderMutations,
    ExportCartMutations,
    ScgpUserManagementMutations,
    RequireAttentionItemsMutations,
    AlternativeMaterialMutations,
    ScgMaterialMutations,
    ScgpPoUploadMutations,
    DtpDtrMutations,
    ScgpPoUploadMasterMappingMutations,
    RealtimePartnerMutations,
    ATPCTPMutations,
    CheckoutATPCTPMutations,
    ExportATPCTPMutations,
    MulesoftAPILogMutations,
    CIPOrderMutation,
    CIPOrderLineMutation,
    CustomerMaterialMutations,
):
    pass


schema = build_federated_schema(
    Query, mutation=Mutation, types=unit_enums, subscription=Subscription
)
