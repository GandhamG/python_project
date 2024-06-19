import graphene


class IPlanInquiryMethodCode(graphene.Enum):
    JIT = "JIT"
    JITP = "JITP"
    JITCP = "JITCP"
    ASAP = "ASAP"


class ParentGroupCode(graphene.Enum):
    ADMIN = "ADMIN"
    CS_DOMESTIC = "CS DOMESTIC"
    CS_EXPORT = "CS EXPORT"
    CUSTOMER = "CUSTOMER"
    CUSTOMER_CIP = "CUSTOMER(CIP)"
    MANAGER = "MANAGER"
    PRODUCTION_PLANNING = "PRODUCTION PLANNING"
    SALES = "SALES"
    SECTION = "SECTION"
    SERVICE_SOLUTION = "SS(SERVICE SOLUTION)"
