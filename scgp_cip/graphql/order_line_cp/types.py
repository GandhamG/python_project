import graphene


class TempOrderLineCP(graphene.ObjectType):
    item_no = graphene.String()
    material_code = graphene.String()
    confirm_date = graphene.Date()
    plant = graphene.String()
