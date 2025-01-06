# templatetags/lead_filters.py
from django import template

register = template.Library()

@register.filter
def filter_by_status(queryset, status):
    return queryset.filter(status=status)