import json
import requests as r
import pickle
import os.path
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from loguru import logger

from utils import create_gcal_event

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

@app.route('/webhook', methods=['POST'])
def main():
    try:
        # Get the JSON data from the request
        data = request.json
        # Check if the calendar id and toggl tokens are present in the request
        if data.keys() != {'calendar_id', 'toggl_token'}:
            return jsonify({"error": "Invalid data"})
        # Check for the header token
        if request.headers.get('Authorization') != 'AxVjWNWt2PqQCw':
            return jsonify({"error": "Unauthorized"})

        calendar_id = data['calendar_id']
        toggl_token = data['toggl_token']

        if not calendar_id or not toggl_token:
            return jsonify({"error": "Invalid data"})

        creds = None
        last_run_entries = None
        first_run = False
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        file_name = f"{calendar_id.split('@')[0]}.pickle"
        custom_path = os.path.abspath("/data")
        token_path = os.path.join(custom_path, 'token.pickle')
        last_entries_path = os.path.join(custom_path, file_name)

        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        if os.path.exists(last_entries_path):
            with open(last_entries_path, 'rb') as token:
                last_run_entries = json.loads(pickle.load(token))

        now = datetime.now().strftime('%Y-%m-%d')
        start_date = datetime.now() - timedelta(days=90)
        start_date = start_date.strftime('%Y-%m-%d')
        service = build('calendar', 'v3', credentials=creds)

        # Check the validity of the calendar id
        try:
            service.calendars().get(calendarId=calendar_id).execute()
        except Exception as e:
            logger.error("Error fetching calendar")
            logger.error(e)
            return jsonify({"error": "Error fetching calendar"})

        # Check the validity of the toggl token
        toggl_time_entries = r.get('https://api.track.toggl.com/api/v9/me/time_entries',
                                   auth=(toggl_token, 'api_token'), params={"start_date": start_date, "end_date": now})

        if toggl_time_entries.status_code != 200:
            logger.error("Error fetching time entries")
            logger.error(f'Status code: {toggl_time_entries.status_code}')
            logger.error(f'Response: {toggl_time_entries.text}')
            return jsonify({"error": "Error fetching time entries", "status_code": toggl_time_entries.status_code,
                            "response": toggl_time_entries.text})

        toggl_time_entries = toggl_time_entries.json()

        if last_run_entries is None:
            with open(last_entries_path, 'wb') as pkl:
                pickle.dump(json.dumps(toggl_time_entries), pkl)
            last_run_entries = toggl_time_entries
            first_run = True

        current_index = len(toggl_time_entries) - len(last_run_entries)

        if current_index == 0 and not first_run:
            logger.info("No new entries")
            return jsonify({"message": "No new entries"})

        if first_run:
            itr = toggl_time_entries
        else:
            itr = last_run_entries[current_index:]

        for entry in itr:
            if entry['duration'] < 0:
                continue
            tags = entry['tags']
            if len(tags) > 1:
                entry['description'] = f"{entry['description']} #{' #'.join(tags)}"
            elif len(tags) == 1:
                entry['description'] = f"{entry['description']} #{tags[0]}"
            event = create_gcal_event(entry['description'], entry['start'], entry['stop'])
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event).execute()
            logger.success(f"Created event: {created_event['id']} on calendar: {calendar_id}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(e)
        return jsonify({"error": "An error occurred"})

if __name__ == '__main__':
    main()
