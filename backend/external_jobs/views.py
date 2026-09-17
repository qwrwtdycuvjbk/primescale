from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q

from external_jobs.models import ExternalJob
from external_jobs.serializers import ExternalJobSerializer


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "results": data,
            }
        )


class ExternalJobListAPIView(generics.ListAPIView):
    """
    Public Endpoint: GET /api/v1/external-jobs/
    Supports filtering by search query, source, remote status, country, technology, and employment_type.
    """

    serializer_class = ExternalJobSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = ExternalJob.objects.filter(is_active=True, status=ExternalJob.Status.ACTIVE)

        params = self.request.query_params

        # Country Filter
        country = params.get("country")
        if country:
            queryset = queryset.filter(country__iexact=country)

        exclude_country = params.get("exclude_country")
        if exclude_country:
            queryset = queryset.exclude(country__iexact=exclude_country)

        # Remote Type Filter (e.g. remote_type=REMOTE,HYBRID or remote_type=REMOTE)
        remote_type_param = params.get("remote_type") or params.get("remote_types")
        if remote_type_param:
            remote_types = [
                t.strip().upper() for t in remote_type_param.split(",") if t.strip()
            ]
            if remote_types:
                queryset = queryset.filter(remote_type__in=remote_types)
        else:
            # Remote Filter (Conservative: remote=true strictly filters for remote_type='REMOTE')
            remote_param = params.get("remote", "").lower()
            if remote_param in ("true", "1", "yes"):
                queryset = queryset.filter(remote_type=ExternalJob.RemoteType.REMOTE)
            elif remote_param in ("false", "0", "no"):
                queryset = queryset.exclude(remote_type=ExternalJob.RemoteType.REMOTE)

        # Source Filter (provider_code or source_name)
        source = params.get("source")
        if source:
            queryset = queryset.filter(
                Q(source__provider_code__iexact=source) | Q(source_name__iexact=source)
            )

        # Technology Filter
        technology = params.get("technology")
        if technology:
            queryset = queryset.filter(tech_stack__icontains=technology)

        # Department Filter
        department = params.get("department")
        if department:
            from external_jobs.utils import get_department_q_filter

            dept_q = get_department_q_filter(department)
            if dept_q:
                queryset = queryset.filter(dept_q)

        # Employment Type Filter
        employment_type = params.get("employment_type")
        if employment_type:
            queryset = queryset.filter(employment_type__icontains=employment_type)

        # General Search Query
        search = params.get("search")
        if search:
            search_terms = search.strip().split()
            for term in search_terms:
                queryset = queryset.filter(
                    Q(title__icontains=term)
                    | Q(company_name__icontains=term)
                    | Q(description__icontains=term)
                    | Q(location__icontains=term)
                )

        return queryset.select_related("source").order_by("-posted_at", "-created_at")
