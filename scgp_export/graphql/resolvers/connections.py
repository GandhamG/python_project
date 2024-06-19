import graphene
from graphql import GraphQLError
from graphql_relay.connection.connectiontypes import Edge, PageInfo

from saleor.graphql.channel import (
    ChannelQsContext,
    ChannelContext
)
from saleor.graphql.channel.utils import get_default_channel_slug_or_graphql_error
from saleor.graphql.core.connection import (
    create_connection_slice,
    _validate_slice_args,
    slice_connection_iterable,
    _validate_connection_args,
    from_global_cursor,
    ConnectionArguments,
    _get_sorting_fields,
    _get_sorting_direction,
    _get_edges_for_connection,
    _prepare_filter_by_rank_expression,
)
from typing import Any, Optional, Tuple, List, Dict, Union
from django.db.models import QuerySet, Q
from graphene.relay import Connection

from saleor.graphql.core.types import SortInputObjectType
from saleor.graphql.utils.sorting import (
    REVERSED_DIRECTION,
    _sort_queryset_by_attribute,
    get_model_default_ordering
)


def resolve_connection_slice(
        qs: QuerySet,
        info,
        kwargs,
        connection_type: Any = Connection,
):
    response = create_connection_slice(qs, info, kwargs, connection_type)

    before = kwargs.get("before")
    first = kwargs.get("first")
    last = kwargs.get("last")

    requested_count = first or last
    total_count = response.total_count()

    if last and not before:
        latest_page_item_number = None
    else:
        total_page = (total_count + requested_count - 1) // requested_count
        if total_page > 1:
            latest_page_item_number = total_count % requested_count if total_count % requested_count != 0 else requested_count
        else:
            latest_page_item_number = total_count
    response.latest_page_item_number = latest_page_item_number

    return response


def resolve_connection_slice_for_overdue(
        qs: QuerySet,
        info,
        kwargs,
        connection_type: Any = Connection,
):
    response = create_connection_slice_for_overdue(qs, info, kwargs, connection_type)

    before = kwargs.get("before")
    first = kwargs.get("first")
    last = kwargs.get("last")

    requested_count = first or last
    total_count = response.total_count()

    if last and not before:
        latest_page_item_number = None
    else:
        total_page = (total_count + requested_count - 1) // requested_count
        if total_page > 1:
            latest_page_item_number = total_count % requested_count if total_count % requested_count != 0 else requested_count
        else:
            latest_page_item_number = total_count
    response.latest_page_item_number = latest_page_item_number

    return response


def _prepare_filter_expression_for_overdue(
        field_name: str,
        index: int,
        cursor: List[str],
        sorting_fields: List[str],
        sorting_direction: str,
        sort_asc_field: bool
) -> Tuple[Q, Dict[str, Union[str, bool]]]:
    field_expression: Dict[str, Union[str, bool]] = {}
    extra_expression = Q()
    for cursor_id, cursor_value in enumerate(cursor[:index]):
        field_expression[sorting_fields[cursor_id]] = cursor_value

    if sorting_direction == "gt":
        # In case Overdue greater than False mean we gonna have overdue == True also
        # but we need to remove it because it already stay at the top of screen
        # so i make the overdue=False and it will remove overdue=True out of the list.
        if field_name == 'overdue' and cursor[0] == 'False' and sort_asc_field:
            extra_expression |= Q(**{f"overdue": False})
            extra_expression |= Q(**{f"{field_name}__isnull": True})
            extra_expression &= Q(**{"pk__gt": cursor[2]})
            if cursor[1]:
                extra_expression &= Q(**{f"{sorting_fields[1]}__gt": cursor[1]})

        else:
            # Default sort
            extra_expression |= Q(**{f"{field_name}__{sorting_direction}": cursor[index]})
            extra_expression |= Q(**{f"{field_name}__isnull": True})
    elif cursor[index] is not None:
        # In case we want to get list before the cursor have overdue == True
        # it means less than True so it gonna have overdue = False .
        # But we don't want to have overdue == False here be cause all overdue == True stay at the top
        # because before an item have overdue == True is all the item have overdue == True
        # so I cut all overdue == False out of the list by pass it, if not the query will be Q('overdue__lt',True)
        if cursor[0] == 'True' and field_name == 'overdue' and sort_asc_field:
            pass
        else:
            # Default sort by graphene
            field_expression[f"{field_name}__{sorting_direction}"] = cursor[index]
    else:
        field_expression[f"{field_name}__isnull"] = False

    return extra_expression, field_expression


def _prepare_filter_for_overdue(
        cursor: List[str], sorting_fields: List[str], sorting_direction: str, first: bool, sort_asc_field: bool
) -> Q:
    """Create filter arguments based on sorting fields.

    :param cursor: list of values that are passed from page_info, used for filtering.
    :param sorting_fields: list of fields that were used for sorting.
    :param sorting_direction: keyword direction ('lt', gt').
    :return: Q() in following format
        (OR: ('first_field__gt', 'first_value_form_cursor'),
            (AND: ('second_field__gt', 'second_value_form_cursor'),
                ('first_field', 'first_value_form_cursor')),
            (AND: ('third_field__gt', 'third_value_form_cursor'),
                ('second_field', 'second_value_form_cursor'),
                ('first_field', 'first_value_form_cursor'))
        )
    """
    if sorting_fields == ["search_rank", "id"]:
        # Fast path for filtering by rank
        return _prepare_filter_by_rank_expression(cursor, sorting_direction)
    filter_kwargs = Q()
    for index, field_name in enumerate(sorting_fields):
        if cursor[index] is None and sorting_direction == "gt":
            continue

        extra_expression, field_expression = _prepare_filter_expression_for_overdue(
            field_name, index, cursor, sorting_fields, sorting_direction, sort_asc_field
        )
        filter_kwargs |= Q(extra_expression, **field_expression)
    # In case we need to get greater than overdue == True,
    # because all item have overdue==True stay at the top so we not gonna have any overdue==False in the list
    # So I put an OR query set so we will still get the item have overdue==False. After that we use sort_by as normal

    if sorting_direction == 'gt' and cursor[0] == 'True' and first:
        filter_kwargs |= Q(**{'overdue': False})
    # In case we need to get less than overdue == False
    # if we get less than False we not gonna have any overdue==True so I put an OR query set
    # so the list will have items with overdue==True
    if sorting_direction == 'lt' and cursor[0] == 'False' and not first:
        filter_kwargs |= Q(('overdue', True))
    return filter_kwargs


def connection_from_queryset_slice_for_overdue(
        qs: QuerySet,
        args: ConnectionArguments = None,
        connection_type: Any = Connection,
        edge_type: Any = Edge,
        pageinfo_type: Any = PageInfo,
) -> Connection:
    """Create a connection object from a QuerySet."""
    args = args or {}
    before = args.get("before")
    after = args.get("after")
    first = args.get("first")
    last = args.get("last")
    _validate_connection_args(args)
    get_first = False
    if first is not None:
        get_first = True
    requested_count = first or last
    end_margin = requested_count + 1 if requested_count else None

    cursor = after or before
    try:
        cursor = from_global_cursor(cursor) if cursor else None
    except ValueError:
        raise GraphQLError("Received cursor is invalid.")

    sort_by = args.get("sort_by", {})
    sorting_fields = _get_sorting_fields(sort_by, qs)
    sort_asc_field = True
    if sort_by.get('direction') == '-':
        sort_asc_field = False
    sorting_direction = _get_sorting_direction(sort_by, last)
    if cursor and len(cursor) != len(sorting_fields):
        raise GraphQLError("Received cursor is invalid.")
    filter_kwargs = (
        _prepare_filter_for_overdue(cursor, sorting_fields, sorting_direction, get_first,
                                    sort_asc_field) if cursor else Q()
    )
    try:
        filtered_qs = qs.filter(filter_kwargs)
    except ValueError:
        raise GraphQLError("Received cursor is invalid.")
    filtered_qs = filtered_qs[:end_margin]
    edges, page_info = _get_edges_for_connection(
        edge_type, filtered_qs, args, sorting_fields
    )

    if "total_count" in connection_type._meta.fields:
        def get_total_count():
            return qs.count()

        return connection_type(
            edges=edges,
            page_info=pageinfo_type(**page_info),
            total_count=get_total_count,
        )

    return connection_type(
        edges=edges,
        page_info=pageinfo_type(**page_info),
    )


def create_connection_slice_for_overdue(
        iterable,
        info,
        args,
        connection_type,
        edge_type=None,
        pageinfo_type=graphene.relay.PageInfo,
        max_limit: Optional[int] = None,
):
    _validate_slice_args(info, args, max_limit)

    if isinstance(iterable, list):
        return slice_connection_iterable(
            iterable,
            args,
            connection_type,
            edge_type,
            pageinfo_type,
        )

    if isinstance(iterable, ChannelQsContext):
        queryset = iterable.qs
    else:
        queryset = iterable

    queryset, sort_by = sort_queryset_for_connection_overdue(iterable=queryset, args=args)
    args["sort_by"] = sort_by

    slice = connection_from_queryset_slice_for_overdue(
        queryset,
        args,
        connection_type,
        edge_type or connection_type.Edge,
        pageinfo_type or graphene.relay.PageInfo,
    )

    if isinstance(iterable, ChannelQsContext):
        edges_with_context = []
        for edge in slice.edges:
            node = edge.node
            edge.node = ChannelContext(node=node, channel_slug=iterable.channel_slug)
            edges_with_context.append(edge)
        slice.edges = edges_with_context

    return slice


def sort_queryset_by_default_overdue(
        queryset: QuerySet, reversed: bool
) -> Tuple[QuerySet, dict]:
    """Sort queryset by it's default ordering."""
    queryset_model = queryset.model
    default_ordering = ["overdue_1", "overdue_2"]
    if queryset_model and queryset_model._meta.ordering:
        default_ordering = get_model_default_ordering(queryset_model)

    ordering_fields = [field.replace("-", "") for field in default_ordering]
    direction = "-" if "-" in default_ordering[0] else ""
    if reversed:
        reversed_direction = REVERSED_DIRECTION[direction]
        default_ordering = [f"{reversed_direction}{field}" for field in ordering_fields]

    order_by = {"field": ordering_fields, "direction": direction}
    return queryset.order_by(*default_ordering), order_by


def sort_queryset_for_connection_overdue(iterable, args):
    sort_by = args.get("sort_by")
    reversed = True if "last" in args else False
    if sort_by:
        iterable = sort_queryset_for_overdue(
            queryset=iterable,
            sort_by=sort_by,
            reversed=reversed,
            channel_slug=args.get("channel")
                         or get_default_channel_slug_or_graphql_error(),
        )
    else:
        iterable, sort_by = sort_queryset_by_default_overdue(
            queryset=iterable, reversed=reversed
        )
        args["sort_by"] = sort_by
    return iterable, sort_by


def check_reversed(input_reversed):
    if input_reversed:
        return ''
    return '-'


def sort_queryset_for_overdue(
        queryset: QuerySet,
        sort_by: SortInputObjectType,
        reversed: bool,
        channel_slug: Optional[str],
) -> QuerySet:
    """Sort queryset according to given parameters.

    rules:
        - sorting_field and sorting_attribute cannot be together)
        - when sorting_attribute is passed, it is expected that
            queryset will have method to sort by attributes
        - when sorter has custom sorting method it's name must be like
            `prepare_qs_for_sort_{enum_name}` and it must return sorted queryset

    Keyword Arguments:
        queryset - queryset to be sorted
        sort_by - dictionary with sorting field and direction

    """
    sorting_direction = sort_by.direction
    if reversed:
        sorting_direction = REVERSED_DIRECTION[sorting_direction]

    sorting_field = sort_by.field
    sorting_attribute = getattr(sort_by, "attribute_id", None)
    if sorting_field is not None and sorting_attribute is not None:
        raise GraphQLError(
            "You must provide either `field` or `attributeId` to sort the products."
        )
    elif sorting_attribute is not None:  # empty string as sorting_attribute is valid
        return _sort_queryset_by_attribute(
            queryset, sorting_attribute, sorting_direction
        )

    sort_enum = sort_by._meta.sort_enum
    sorting_fields = sort_enum.get(sorting_field)
    sorting_field_name = sorting_fields.name.lower()

    custom_sort_by = getattr(sort_enum, f"qs_with_{sorting_field_name}", None)
    if custom_sort_by:
        queryset = custom_sort_by(queryset, channel_slug=channel_slug)

    sorting_field_value = sorting_fields.value
    sorting_list = [f"{sorting_direction if field not in ['overdue'] else check_reversed(reversed)}{field}" for
                    field in sorting_field_value]

    return queryset.order_by(*sorting_list)
