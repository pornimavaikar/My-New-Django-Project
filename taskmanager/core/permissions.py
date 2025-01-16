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
        print("\n=== Role Required Mixin Debug ===")
        print(f"Testing permissions for user: {self.request.user.username}")
        print(f"User role: {self.request.user.role}")
        print(f"Required roles: {self.roles_required}")
        has_permission = self.request.user.role in self.roles_required
        print(f"Permission granted: {has_permission}")
        return has_permission
    
    def handle_no_permission(self):
        print("\n=== Permission Denied ===")
        print(f"Access denied for user: {self.request.user.username}")
        print(f"User role: {self.request.user.role}")
        raise PermissionDenied("You do not have permission to access this page.")

def get_leads_for_user(user):
    """
    Get leads based on user role, hierarchy, and task assignments
    """
    if user.role == 'ADMIN':
        return Lead.objects.all()
        
    elif user.role == 'TL':
        # Get all users in TL's hierarchy (SRMs and their RMs)
        team_members = CustomUser.objects.filter(
            Q(reporting_to=user) |  # Direct reports (SRMs)
            Q(reporting_to__reporting_to=user)  # Indirect reports (RMs under SRMs)
        )
        return Lead.objects.filter(
            Q(assigned_to__in=team_members) |  # Leads assigned to team members
            Q(assigned_to=user) |  # Leads assigned to TL
            Q(task__assigned_by__in=team_members) |  # Leads from tasks created by team
            Q(task__assigned_by=user) |  # Leads from tasks created by TL
            Q(task__assigned_to__in=team_members)  # Leads from tasks assigned to team
        ).distinct()
        
    elif user.role == 'SRM':
        # Get all RMs under SRM
        team_members = CustomUser.objects.filter(
            Q(reporting_to=user) |  # Direct reports (RMs)
            Q(id=user.id)  # Include SRM themselves
        )
        return Lead.objects.filter(
            Q(assigned_to__in=team_members) |  # Leads assigned to team
            Q(task__assigned_by=user) |  # Leads from tasks created by SRM
            Q(task__assigned_to__in=team_members) |  # Leads from tasks assigned to team
            Q(task__assigned_to=user)  # Leads from tasks assigned to SRM
        ).distinct()
        
    else:  # RM
        return Lead.objects.filter(
            Q(assigned_to=user) |  # Leads assigned to RM
            Q(task__assigned_to=user)  # Leads from tasks assigned to RM
        ).distinct()