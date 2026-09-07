from django.urls import path
from .views import HandoffDetailView, HandoffQueueView

app_name = "handoffs"

urlpatterns = [
    path("", HandoffQueueView.as_view(), name="handoff_queue"),
    path("<uuid:pk>/", HandoffDetailView.as_view(), name="handoff_detail"),
]
