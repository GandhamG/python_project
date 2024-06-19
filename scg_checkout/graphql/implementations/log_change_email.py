from saleor.plugins import manager
from sap_migration import models


def alternative_material_outsource_failed_change(info, order_id, error_items):
    try:
        order = models.Order.objects.filter(pk=order_id).first()
        sold_to_code_name = f"{order.contract.sold_to.sold_to_code}-{order.contract.sold_to.sold_to_name}"
        template_data = {
            'order': models.Order.objects.filter(pk=order_id).first(),
            'so_no': order.so_no,
            'po_no': order.po_no,
            'sold_to_code_name': sold_to_code_name,
            'order_no': order.order_no,
            'ship_to_code_name': order.contract.ship_to,
            'contract_no': order.contract.code,
            'request_delivery_date': order.request_delivery_date,
            'item_no': "10",
            'item_errors': error_items  # dict error { material_id : error}
        }
        manager = info.context.plugins
        manager.scgp_po_upload_send_mail_when_call_api_fail(
            "scg.email",
            recipient_list=["ducdm1@smartosc.com"],
            subject=f"[Error Change Mat OS] [{order.so_no}] [{order.po_no}] [{sold_to_code_name}]",
            template="alternative_outsource_failed_change.html",
            template_data=template_data,
            cc_list=[],
        )
    except Exception as e:
        raise e
