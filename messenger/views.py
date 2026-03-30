from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from .models import Thread, Message
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseForbidden

User = get_user_model()

@staff_member_required
def messenger_home(request):
    # SaaS Privacy: SuperAdmin should not be part of resort-level operational chat
    if request.user.role == User.Role.SUPERADMIN:
        return render(request, 'messenger/restricted.html', {
            'site_title': "Internal Messenger",
            'reason': "Access Restricted: Messenger is strictly for resort operational staff to maintain data privacy."
        })

    # Resort Isolation: Only show threads for the user's specific resort
    resort = request.user.resort
    if not resort:
        return render(request, 'messenger/restricted.html', {
            'site_title': "Internal Messenger",
            'reason': "You are not associated with any resort and cannot access the messenger."
        })

    threads = Thread.objects.filter(
        participants=request.user,
        resort=resort
    ).order_by('-updated_at')
    
    # Exclude SuperAdmins and Owners from the staff chat list
    # Filter by the SAME resort for isolation
    available_users = User.objects.filter(
        resort=resort
    ).exclude(
        id=request.user.id
    ).exclude(
        role__in=[User.Role.SUPERADMIN, User.Role.OWNER]
    ).order_by('fullname')

    return render(request, 'messenger/index.html', {
        'threads': threads,
        'available_users': available_users,
        'site_title': "Internal Messenger",
    })

@staff_member_required
def thread_detail(request, thread_id):
    # Enforce resort isolation in the lookup
    thread = get_object_or_404(Thread, id=thread_id, participants=request.user, resort=request.user.resort)
    messages = thread.messages.all()
    
    # Get other participant (for 1v1)
    other_user = thread.participants.exclude(id=request.user.id).first()
    
    return render(request, 'messenger/thread.html', {
        'thread': thread,
        'chat_messages': messages,
        'other_user': other_user,
    })

@staff_member_required
def create_direct_thread(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    
    # Privacy Check: Cannot start chat with SuperAdmin or Owner, and must be same resort
    if other_user.role in [User.Role.SUPERADMIN, User.Role.OWNER] or other_user.resort != request.user.resort:
        return HttpResponseForbidden("Privacy Violation: You cannot start a chat with this user.")

    # Check if a direct thread already exists in this resort context
    thread = Thread.objects.filter(
        thread_type=Thread.Type.DIRECT,
        resort=request.user.resort,
        participants=request.user
    ).filter(
        participants=other_user
    ).first()
    
    if not thread:
        thread = Thread.objects.create(
            thread_type=Thread.Type.DIRECT,
            resort=request.user.resort
        )
        thread.participants.add(request.user, other_user)
        
    return redirect('messenger:thread_detail', thread_id=thread.id)
