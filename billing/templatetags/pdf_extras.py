from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Dict lookup by a variable key — Django's `.` lookup only supports
    literal keys, needed for the Arabic charge-type label maps used across
    every bilingual PDF template."""
    return dictionary.get(key, key)
