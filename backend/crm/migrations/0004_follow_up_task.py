import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0003_lead_sales_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FollowUpTask",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=120)),
                ("details", models.CharField(blank=True, default="", max_length=500)),
                ("due_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="pending", max_length=12)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_followups", to=settings.AUTH_USER_MODEL)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="crm.lead")),
            ],
            options={"ordering": ["due_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="followuptask",
            index=models.Index(fields=["status", "due_at"], name="task_status_due_idx"),
        ),
        migrations.AddIndex(
            model_name="followuptask",
            index=models.Index(fields=["lead", "status", "due_at"], name="task_lead_status_due_idx"),
        ),
        migrations.AddConstraint(
            model_name="followuptask",
            constraint=models.CheckConstraint(condition=models.Q(("title__regex", r"\S")), name="task_title_not_blank"),
        ),
        migrations.AddConstraint(
            model_name="followuptask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("cancelled_at__isnull", True), ("completed_at__isnull", True), ("status", "pending")),
                    models.Q(("cancelled_at__isnull", True), ("completed_at__isnull", False), ("status", "completed")),
                    models.Q(("cancelled_at__isnull", False), ("completed_at__isnull", True), ("status", "cancelled")),
                    _connector="OR",
                ),
                name="task_status_timestamps_match",
            ),
        ),
    ]
