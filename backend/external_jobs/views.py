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

        # Country Filter (Defaults to US if requested or unspecified in common searches)
        country = params.get("country")
        if country:
            queryset = queryset.filter(country__iexact=country)

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
