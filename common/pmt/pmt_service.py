import logging

from django.core.exceptions import ImproperlyConfigured, ValidationError

from common.mulesoft_api import MulesoftApiError
from common.pmt.pmt_api import PmtApiRequest
from common.pmt.pmt_helper import (
    formatted_pmt_api_response,
    prepare_param_for_pmt_mat_search,
)


def mat_search_by_pmt(input_data):
    try:
        logging.info(f"[Mat Search] via PMT API with filters: {input_data}")
        params = prepare_param_for_pmt_mat_search(input_data)
        api_response = PmtApiRequest.call_pmt_mat_search(params)
        data = api_response.get("result")
        if not data:
            return []
        response = formatted_pmt_api_response(data)
        logging.info(f"[Mat Search] via PMT API COMPLETED with filters: {input_data}")
        return response
    except ValidationError as e:
        raise e
    except MulesoftApiError as e:
        raise e
    except Exception as e:
        raise ImproperlyConfigured(e)
