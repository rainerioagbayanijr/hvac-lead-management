from django.urls import path

from .views import (
    AddNoteView,
    AssignLeadView,
    CancelTaskView,
    ChangeStageView,
    ClaimLeadView,
    CompleteTaskView,
    InquiryView,
    LeadDetailView,
    LeadListView,
    RecordContactView,
    ReopenLeadView,
    RescheduleTaskView,
    ScheduleTaskView,
    TaskListView,
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
    path("tasks/", TaskListView.as_view()),
    path("leads/<uuid:pk>/tasks/", ScheduleTaskView.as_view()),
    path("leads/<uuid:lead_pk>/tasks/<uuid:task_pk>/reschedule/", RescheduleTaskView.as_view()),
    path("leads/<uuid:lead_pk>/tasks/<uuid:task_pk>/complete/", CompleteTaskView.as_view()),
    path("leads/<uuid:lead_pk>/tasks/<uuid:task_pk>/cancel/", CancelTaskView.as_view()),
    path("team/", TeamView.as_view()),
]
