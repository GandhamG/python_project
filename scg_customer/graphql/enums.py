import graphene
from customer import error_codes as customer_error_codes

CustomerErrorCode = graphene.Enum.from_enum(customer_error_codes.CustomerErrorCode)
