from django import template

from apps.driver_help.display import help_author_label

register = template.Library()


@register.filter
def help_author_display(user):
    return help_author_label(user)
