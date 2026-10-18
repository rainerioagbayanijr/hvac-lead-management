from django.db import models


class RateLimitBucket(models.Model):
    scope = models.CharField(max_length=40)
    subject_hash = models.CharField(max_length=64)
    bucket_start = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "subject_hash", "bucket_start"], name="rate_bucket_unique"
            ),
        ]
