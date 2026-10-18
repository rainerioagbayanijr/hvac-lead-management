from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Read-only until workflow services can enforce all mutations."""

    list_display = ("name", "service_type", "stage", "owner", "received_at")
    list_filter = ("stage", "service_type", "source")
    search_fields = ("name", "phone", "email")
    readonly_fields = tuple(field.name for field in Lead._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
