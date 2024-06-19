import graphene


class IPlanYT65156Message(graphene.ObjectType):
    item_no = graphene.String()
    first_code = graphene.String()
    second_code = graphene.String()
    message = graphene.String()
