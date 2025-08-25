from django import template
register = template.Library()

@register.filter
def index(List, i):
    try:
        return List[int(i)]
    except Exception as e:
        return ''


@register.filter(name='zip_lists')
def zip_lists(a, b):
    return zip(a, b)
