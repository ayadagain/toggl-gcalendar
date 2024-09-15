def create_gcal_event(summary, start, end, timezone='UTC'):
    return {
        'summary': summary,
        'start': {
            'dateTime': start,
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end,
            'timeZone': timezone,
        },
    }