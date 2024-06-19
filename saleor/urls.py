from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from scg_checkout.graphql.implementations.orders import i_plan_update_order

from .core.upload_user import upload_user_data
from .core.views import (
    eo_data_trigger,
    get_eo_number,
    get_so_number,
    jwks,
    log_mulesoft_api,
    receive_eo_data,
    test_process_eo_upload,
)
from .graphql.api import schema
from .graphql.views import GraphQLView
from .plugins.views import (
    handle_global_plugin_webhook,
    handle_plugin_per_channel_webhook,
    handle_plugin_webhook,
)
from .product.views import digital_product

urlpatterns = [
    url(
        r"graphql/webhooks/run-task-eo-upload",
        test_process_eo_upload,
        name="run_task_eo_upload",
    ),  # XXX: remove later
    url(r"graphql/webhooks/eo_data_trigger", eo_data_trigger, name="eo_data_trigger"),
    url(r"api/eo-upload", receive_eo_data, name="eo_data_upload"),
    url(r"api/get-eo-number", get_eo_number, name="get_eo_number"),
    path("api/v1/salesOrder/temporder/<id>", get_so_number, name="get_so_number"),
    url(r"^api/upload_user_data", upload_user_data, name="update_user_data"),
    url("api/log-mulesoft", log_mulesoft_api, name="log_mulesoft_api"),
    url(r"^graphql/$", csrf_exempt(GraphQLView.as_view(schema=schema)), name="api"),
    url(
        r"^digital-download/(?P<token>[0-9A-Za-z_\-]+)/$",
        digital_product,
        name="digital-product",
    ),
    url(
        r"plugins/channel/(?P<channel_slug>[.0-9A-Za-z_\-]+)/"
        r"(?P<plugin_id>[.0-9A-Za-z_\-]+)/",
        handle_plugin_per_channel_webhook,
        name="plugins-per-channel",
    ),
    url(
        r"plugins/global/(?P<plugin_id>[.0-9A-Za-z_\-]+)/",
        handle_global_plugin_webhook,
        name="plugins-global",
    ),
    url(
        r"plugins/(?P<plugin_id>[.0-9A-Za-z_\-]+)/",
        handle_plugin_webhook,
        name="plugins",
    ),
    url(r".well-known/jwks.json", jwks, name="jwks"),
    url(r"api/y2", i_plan_update_order, name="i_plan_update_order"),
]

if settings.DEBUG:
    import warnings

    from .core import views

    try:
        import debug_toolbar
    except ImportError:
        warnings.warn(
            "The debug toolbar was not installed. Ignore the error. \
            settings.py should already have warned the user about it."
        )
    else:
        urlpatterns += [
            url(r"^__debug__/", include(debug_toolbar.urls))  # type: ignore
        ]

    urlpatterns += static("/media/", document_root=settings.MEDIA_ROOT) + [
        url(r"^static/(?P<path>.*)$", serve),
        url(r"^", views.home, name="home"),
    ]
