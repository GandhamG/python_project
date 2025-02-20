from typing import Dict

import graphene

federated_entities: Dict[str, graphene.ObjectType] = {}


def federated_entity(key_fields: str):
    def federate_entity(graphql_type: graphene.ObjectType):
        # Add entity to registry
        federated_entities[graphql_type.__name__] = graphql_type

        # Override it's SDL to contain federation's @key directive
        type_sdl: str = getattr(graphql_type, "_sdl", "")
        key_sdl = f'@key(fields: "{key_fields}")'

        if type_sdl:
            type_sdl = f"{key_sdl} {type_sdl}"
        else:
            type_sdl = key_sdl

        setattr(graphql_type, "_sdl", type_sdl)  # NOQA

        return graphql_type

    return federate_entity
