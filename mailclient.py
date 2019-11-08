from __future__ import print_function
import pickle
import os.path
import sqlite3
import datetime
import re
import time
from sqlite import create_db, insert_event, get_event, get_events
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


# TODO hvad hvis folk kommer til at købe noget, standse ved en fejl, og så tage den igen. Det tæller som 2 køb, men gælder faktisk kun for 1.
# TODO errorhandling. Program ree's if there are no more mails that match the search
# TODO better way to handle the naive no-work. Perhaps see if there are any unread

# Sets up connection to gmail
def setupConnection():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
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
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


# Converts the timestamp in mail for dispenseEvent to unix timestamp
def getUnixTime(time):
    # Get all numbers from the snippet
    array = list(map(int, re.findall(r'[0-9]+', time)))

    # Convert to unix timestamp in correct order. Might be a better solution.
    # (mail is in DD/MM/YY, function is in (YY/MM/DD, therefore the weird indexes)
    return int(datetime.datetime(array[2], array[1], array[0], array[3], array[4], array[5]).timestamp())


# Return the name of the first drink
def getDrink(event):
    return re.findall("(?<=;)[a-zA-Z é]*(?=&)", event)[0]


def addUnreadDispensedDrinkEvent(gmail_con, db_conn, search):
    # Get all mails that match the search
    inbox = gmail_con.users().messages().list(userId='me', q=search, maxResults=20).execute()

    # Gets information from mails in "minimal" format, as only a snippet of the mail is needed
    # (recent event is in start of mail)
    try:
        mails = [gmail_con.users().messages().get(userId="me", id=msg['id'], format="minimal").execute() for msg in
                 inbox["messages"]]

        # Array to hold ids of mails to remove "unread"- label
        idsToModify = []

        for mail in mails:
            # Add the DispensedDrinkEvent to db
            insert_event(db_conn, getUnixTime(mail["snippet"]), "DispensedDrinkEvent", getDrink(mail["snippet"]))

            # Append id to array
            idsToModify.append(mail['id'])

        # Remove "unread"- label on all mails in array
        gmail_con.users().messages().batchModify(userId='me',
                                                 body={'removeLabelIds': ['UNREAD'], 'addLabelIds': [],
                                                       'ids': idsToModify}).execute()
    except:
        print("No more unread DispensedDrinkEvents")


def main():
    gmail_con = setupConnection()

    # Create database
    db_conn = sqlite3.connect('jvm-loss.db')
    create_db(db_conn, True, True)

    search = 'label:dispenseddrinkevent is:unread'

    while True:
        currentHour = datetime.datetime.now().hour
        currentDay = datetime.datetime.now().isoweekday()

        print(f"Hour: {currentHour}, day: {currentDay}")

        # During working hours, check every 10mins, else wait an hour and check again
        if (7 <= currentHour <= 16) and (1 <= currentDay <= 5):
            print("Checking for unread dispense-events")
            addUnreadDispensedDrinkEvent(gmail_con, db_conn, search)
            time.sleep(1)
        else:
            print("Not within working hours, waiting for an hour")
            time.sleep(3600)


if __name__ == '__main__':
    main()
