from django.urls import path

from .views import (
    AddNoteView,
    AssignLeadView,
    ChangeStageView,
    ClaimLeadView,
    InquiryView,
    LeadDetailView,
    LeadListView,
    RecordContactView,
    ReopenLeadView,
    TeamView,
)

urlpatterns = [
    path("inquiries/", InquiryView.as_view()),
    path("leads/", LeadListView.as_view()),
    path("leads/<uuid:pk>/", LeadDetailView.as_view()),
    path("leads/<uuid:pk>/claim/", ClaimLeadView.as_view()),
    path("leads/<uuid:pk>/assignment/", AssignLeadView.as_view()),
    path("leads/<uuid:pk>/contact/", RecordContactView.as_view()),
    path("leads/<uuid:pk>/stage/", ChangeStageView.as_view()),
    path("leads/<uuid:pk>/reopen/", ReopenLeadView.as_view()),
    path("leads/<uuid:pk>/notes/", AddNoteView.as_view()),
    path("team/", TeamView.as_view()),
]
