from django import template

register = template.Library()

@register.filter
def has_role(user, roles):
    """Check if user has any of the specified roles"""
    if not user.is_authenticated:
        return False
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(',')]
    return user.role in roles