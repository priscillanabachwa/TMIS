from decimal import Decimal

from django import template
from django.utils.html import format_html

register = template.Library()

STATUSES = {
    'active': 'success', 'confirmed': 'success', 'paid': 'success',
    'completed': 'success', 'present': 'success', 'issued': 'success',
    'delivered': 'success', 'pending': 'warning', 'partially paid': 'warning',
    'postponed': 'warning', 'late': 'warning', 'scheduled': 'info',
    'sent': 'info', 'replaced': 'info', 'excused': 'info',
    'inactive': 'neutral', 'archived': 'neutral', 'withdrawn': 'neutral',
    'cancelled': 'danger', 'failed': 'danger', 'reversed': 'danger',
    'revoked': 'danger', 'absent': 'danger', 'suspended': 'danger',
}


@register.filter
def display_cell(value):
    if isinstance(value, Decimal):
        return format(value, ',.2f')
    if isinstance(value, str) and value in STATUSES:
        return format_html('<span class="badge badge-{}">{}</span>',
                           STATUSES[value], value.title())
    return value
