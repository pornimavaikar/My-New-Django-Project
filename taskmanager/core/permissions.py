# core/permissions.py
from django.contrib.auth.mixins import UserPassesTestMixin
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import Lead

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

def get_leads_for_user(user):
    """
    Helper function to get leads based on user role
    Args:
        user: CustomUser instance
    Returns:
        QuerySet of leads accessible to the user
    """
    if user.role == 'ADMIN':
        return Lead.objects.all()
    elif user.role == 'TL':
        return Lead.objects.filter(
            Q(assigned_to__reporting_to=user) | 
            Q(assigned_to__reporting_to__reporting_to=user)
        )
    elif user.role == 'SRM':
        return Lead.objects.filter(assigned_to__reporting_to=user)
    else:  # RM
        return Lead.objects.filter(assigned_to=user)