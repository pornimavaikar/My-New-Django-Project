# core/permissions.py
from django.contrib.auth.mixins import UserPassesTestMixin
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import Lead,CustomUser
def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.role in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return wrapped
    return decorator

class RoleRequiredMixin(UserPassesTestMixin):
    roles_required = []

    def test_func(self):
        return self.request.user.role in self.roles_required

# In permissions.py

def get_leads_for_user(user):
    """
    Get leads based on user role and hierarchy
    """
    if user.role == 'ADMIN':
        return Lead.objects.all()
    
    elif user.role == 'TL':
        # Get all users reporting to TL (directly or indirectly)
        team_members = CustomUser.objects.filter(
            Q(reporting_to=user) |  # Direct reports (SRMs)
            Q(reporting_to__reporting_to=user)  # Indirect reports (RMs under SRMs)
        )
        return Lead.objects.filter(
            Q(assigned_to__in=team_members) |
            Q(assigned_to=user)
        )
    
    elif user.role == 'SRM':
        # Get all RMs reporting to SRM and leads assigned to them
        team_members = CustomUser.objects.filter(
            Q(reporting_to=user) |  # Direct reports (RMs)
            Q(id=user.id)  # Include SRM themselves
        )
        # Get leads from tasks assigned to the SRM or their team
        return Lead.objects.filter(
            Q(assigned_to__in=team_members) |
            Q(task__assigned_to__in=team_members)
        ).distinct()
    
    else:  # RM
        # Get leads directly assigned to RM or from tasks assigned to them
        return Lead.objects.filter(
            Q(assigned_to=user) |
            Q(task__assigned_to=user)
        ).distinct()