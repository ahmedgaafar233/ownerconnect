from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Thread(models.Model):
    class Type(models.TextChoices):
        DIRECT = "DIRECT", _("Direct")
        GROUP = "GROUP", _("Group")

    thread_type = models.CharField(max_length=10, choices=Type.choices, default=Type.DIRECT)
    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="threads", null=True, blank=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="chat_threads")
    title = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.title:
            return self.title
        return f"Thread {self.id} ({self.thread_type})"

class Message(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Message from {self.sender} at {self.created_at}"

class Attachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="chat_attachments/")
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename
