import uuid


def add_key_and_data_into_params(key, value, params):
    if not value:
        return
    params[key] = value


def get_random_number():
    return str(uuid.uuid1().int)
