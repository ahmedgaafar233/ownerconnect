# OwnerConnect Copilot Instructions

## Overview
OwnerConnect is a Django-based resort management system for Delta Sharm Resort. It handles billing, user management, support tickets, and Excel imports for a vacation resort with multiple units owned by users.

## Architecture
- **Apps**: `core` (Resort/Unit models), `users` (custom User with phone auth + roles), `billing` (Charge/Payment workflow), `imports` (Excel upload processing), `support` (ticket system)
- **Authentication**: Phone-based with JWT; roles auto-sync to Django Groups
- **Database**: SQLite default; Docker Compose provides Postgres + Redis
- **Admin**: Custom Unfold theme with resort-specific navigation

## Development Workflow
- **Setup**: Run `start_server.bat` (Windows) or `python manage.py runserver` after `pip install -r requirements.txt && python manage.py migrate`
- **Superuser**: Phone `01000000000`, password `admin123` (created by `create_superuser.py`)
- **Desktop App**: `python desktop/run.py` launches webview window
- **API Docs**: `/api/docs/` (Swagger UI)

## Key Patterns
- **Charge Workflow**: PENDING → REVIEWED → PUBLISHED/REJECTED; use `charge.publish(by_user)` method
- **User Roles**: SUPERADMIN/GENERAL_MANAGER/FINANCIAL_MANAGER/SUPERVISOR/DATA_ENTRY/RECEPTION/OWNER; roles set `is_staff`/`is_superuser`
- **Owner Queries**: Use `OwnerUnit` join; e.g., `Charge.objects.filter(unit__owner_units__owner=user)`
- **Services**: Business logic in `BillingService` (e.g., `get_unit_statement`, `get_owner_charges`)
- **Excel Import**: Via admin wizard; processes to `Charge` with `source_upload`/`source_row` tracking
- **Ticket System**: Status workflow with auto-generated mobile IDs; overdue based on priority

## Common Tasks
- **Add Charge**: Create via admin or import; set `status=PENDING`, approve to `PUBLISHED`
- **User Balance**: `user.total_debt - user.total_paid` (aggregates across owned units)
- **Unit Statement**: Use `BillingService.get_unit_statement(unit)` for annotated charges + totals
- **Permissions**: Check `user.role` or `user.groups`; owners see only their units' data

## Examples
- **Filter Owner Charges**: `Charge.objects.filter(unit__owner_units__owner=request.user, status=Charge.Status.PUBLISHED)`
- **Create Payment**: `Payment.objects.create(charge=charge, amount=Decimal('100.00'))`
- **Assign Ticket**: `ticket.assigned_to = staff_user; ticket.status = Ticket.Status.ASSIGNED; ticket.save()`