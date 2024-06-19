from datetime import datetime


def convert_date_format(input_date, input_format, output_format):
    if not input_date:
        return ""
    # Convert string to datetime object
    dt_object = convert_string_to_datetime(input_date, input_format)
    # Format datetime object as string
    output_string = dt_object.strftime(output_format)
    return output_string


def convert_date_format_date_type(input_date, input_format, output_format):
    if not input_date:
        return ""
    # Convert string to datetime object
    dt_object = convert_string_to_datetime(input_date, input_format)
    # Format datetime object as string
    output_string = dt_object.strftime(output_format)
    output_date = datetime.strptime(output_string, output_format).date()
    return output_date


def convert_string_to_datetime(input_date, input_format):
    dt_object = (
        datetime.strptime(input_date, input_format)
        if isinstance(input_date, str)
        else input_date
    )
    return dt_object
