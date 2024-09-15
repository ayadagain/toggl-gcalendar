def create_gcal_event(summary, start, end):
    return {
        'summary': summary,
        'start': {
            'dateTime': start,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end,
            'timeZone': 'UTC',
        },
    }