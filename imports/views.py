import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django import forms

from .models import ImportSource, ExcelUpload
from core.models import Unit, Resort
from billing.models import Charge
from .services import process_excel_upload
from users.models import User

class ImportWizardView(UserPassesTestMixin, View):
    template_name = "admin/imports/wizard.html"

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.role in [
            User.Role.DATA_ENTRY,
            User.Role.SUPERVISOR,
            User.Role.FINANCIAL_MANAGER,
            User.Role.GENERAL_MANAGER,
        ]

    def get(self, request):
        sources = ImportSource.objects.filter(is_active=True)
        # Cross-tenant fix: don't list another resort's import sources to a
        # non-superuser — that would leak the existence/naming of another
        # resort's data-entry configuration and hand them a source_id to
        # replay against handle_upload.
        if not request.user.is_superuser:
            sources = sources.filter(resort=request.user.resort)
        return render(request, self.template_name, {"step": "upload", "sources": sources})

    def post(self, request):
        step = request.POST.get("step")
        
        if step == "upload":
            return self.handle_upload(request)
        elif step == "commit":
            return self.handle_commit(request)
        
        return redirect("admin:index")

    def handle_upload(self, request):
        file = request.FILES.get("file")
        source_id = request.POST.get("source_id")
        
        if not file or not source_id:
            messages.error(request, "Please select a file and a source.")
            return redirect(request.path)

        source = get_object_or_404(ImportSource, id=source_id)

        # Cross-tenant fix: source_id is client-supplied. Without this check a
        # DATA_ENTRY/SUPERVISOR user from resort A could submit a source_id
        # belonging to resort B and have their uploaded charges created
        # against resort B's units — a cross-tenant data-injection IDOR.
        if not request.user.is_superuser and source.resort_id != request.user.resort_id:
            messages.error(request, "You do not have permission to use this import source.")
            return redirect(request.path)

        # Save temp file
        upload = ExcelUpload.objects.create(
            resort=source.resort,
            source=source,
            file=file,
            original_name=file.name,
            status="UPLOADED"
        )
        
        # Parse preview
        try:
            df = pd.read_excel(upload.file.path)
            # Basic validation logic (simplified for demo)
            preview_data = df.head(10).to_dict(orient="records")
            columns = df.columns.tolist()
            
            return render(request, self.template_name, {
                "step": "preview",
                "upload": upload,
                "preview_data": preview_data,
                "columns": columns,
                "total_rows": len(df)
            })
        except Exception as e:
            upload.status = "FAILED"
            upload.error = str(e)
            upload.save()
            messages.error(request, f"Error reading file: {e}")
            return redirect(request.path)

    def handle_commit(self, request):
        upload_id = request.POST.get("upload_id")
        upload = get_object_or_404(ExcelUpload, id=upload_id)

        # Cross-tenant fix: without this, any authorized role could commit
        # (turn into real Charge rows) an upload_id belonging to a resort they
        # don't work for, simply by guessing/incrementing the id.
        if not request.user.is_superuser and upload.resort_id != request.user.resort_id:
            messages.error(request, "You do not have permission to process this upload.")
            return redirect("admin:imports_excelupload_changelist")

        year = request.POST.get("year")
        month = request.POST.get("month")

        try:
            with transaction.atomic():
                # Keep charges as PENDING until Financial/GM publishes them.
                result = process_excel_upload(upload, year_override=year, month_override=month)

            if result.get("errors"):
                messages.error(request, f"Processed with errors: {len(result['errors'])}")
            else:
                messages.success(request, f"Successfully created {result.get('created', 0)} charges (Pending Approval).")

        except Exception as e:
            upload.status = "FAILED"
            upload.error = str(e)
            upload.save(update_fields=["status", "error"])
            messages.error(request, f"Processing failed: {e}")
            
        return redirect("admin:imports_excelupload_changelist")
