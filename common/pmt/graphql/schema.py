import graphene

from common.pmt.graphql.resolves.resolver import resolve_pmt_mat_search
from common.pmt.graphql.types import PmtMatSearchInput, PmtMatSearch


class PMTQueries(graphene.ObjectType):
    pmt_mat_search = graphene.List(
        PmtMatSearch,
        filter=graphene.Argument(PmtMatSearchInput)
    )

    @staticmethod
    def resolve_pmt_mat_search(self, info, **kwargs):
        return resolve_pmt_mat_search(kwargs.get('filter'))
