from django.urls import path

from .views import InquiryView, LeadDetailView, LeadListView

urlpatterns = [
    path("inquiries/", InquiryView.as_view()),
    path("leads/", LeadListView.as_view()),
    path("leads/<uuid:pk>/", LeadDetailView.as_view()),
]
