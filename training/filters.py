def filter_status(request, rows, field):
    choices = list(rows.model._meta.get_field(field).choices)
    selected = request.GET.get('status', '')
    if selected not in dict(choices):
        selected = ''
    if selected:
        rows = rows.filter(**{field: selected})
    return rows, {'status': selected, 'status_options': choices}
