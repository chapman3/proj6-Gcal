import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid

import json
import logging

# Date handling 
import arrow # Replacement for datetime, based on moment.js
import datetime # But we still need time
from dateutil import tz  # For interpreting local times

#agenda
import agenda

# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services 
from apiclient import discovery

###
# Globals
###
import CONFIG
app = flask.Flask(__name__)

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = "client_secret.json"  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'

#############################
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
  app.logger.debug("Entering index")
  if 'begin_date' not in flask.session:
    init_session_values()
  return render_template('index.html')

@app.route("/choose")
def choose():
    ## We'll need authorization to list calendars 
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return' 
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    ##Store Calendars
    flask.session['calendars'] = list_calendars(gcal_service)
    return render_template('index.html')

@app.route("/busy")
def busy():
    return render_template('busy.html')

@app.route("/response")
def response():
    return render_template('response.html')


####
#
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST: 
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable. 
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead. 
#
####

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value. 
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
        credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service

@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function. 
  
  ## The *second* time we enter here, it's a callback 
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1. 
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use. 
#
#####

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    Assumptions:
        User chose a daterange with the bootstrap daterange widget.
        User entered a Meeting Description
        User entered a Meeting Location
        User entered a Meeting Timerange by supplying a possible start and end time for a meeting
        User entered a Meeting Duration

    args: none
    returns: redirect to url_for("choose")

    Process:
        Store all prerequisite data in a session object.
    """
    app.logger.debug("Entering setrange")
    flask.flash("Setrange gave us '{}'".format(
      request.form.get('daterange')))
    daterange = request.form.get('daterange')
    flask.session['daterange'] = daterange
    daterange_parts = daterange.split()
    print(daterange_parts[0])
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      daterange_parts[0], daterange_parts[1],
      flask.session['begin_date'], flask.session['end_date']))
    flask.session['meet_desc'] = request.form.get('meet_desc')
    flask.session['meet_loc'] = request.form.get('meet_loc')
    flask.session['meet_range_start'] = interpret_time(request.form.get('meet_range_start'))
    flask.session['meet_range_end'] = interpret_time(request.form.get('meet_range_end'))
    flask.session['meet_dur'] = request.form.get('meet_dur')
    #temp_time = arrow.get(flask.session['meet_range_start']).replace(daterange_parts[0])
    #print(temp_time)
    return flask.redirect(flask.url_for("choose"))

@app.route('/showBusyFree', methods=['POST'])
def showBusyFree():

    """
    assumptions:
        times have been chosen
    args:
        none
    returns:
        none
    """
    print("made it to showBusyFree")
    flask.session['cal_selection'] = request.args.getlist('selection')
    #print(flask.session['cal_selection'])
    #print(flask.session['calendars'])
    createBusyList()
    createFreeList()
    return flask.redirect(flask.url_for("busy"))

@app.route('/showConfirm', methods=['POST'])
def showConfirm():
    return flask.redirect(flask.url_for("response"))

####
#
#   Initialize session variables 
#
####

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main. 
    """
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)
    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    # Default time span each day, 8 to 5
    flask.session["begin_time"] = interpret_time("9am")
    flask.session["end_time"] = interpret_time("5pm")

def interpret_time( text ):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try: 
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
              .format(text))
        raise
    return as_arrow.isoformat()

def interpret_date( text ):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
      as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
          tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format 12/31/2001")
        raise
    return as_arrow.isoformat()

def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####

def createBusyList():
    """
    assumptions:
        user has pulled in calendars
    args:
        none
    returns:
        stores busy list in session
    """
    print("Made it to createBusyList")
    busy_list = []
    busy_list_display = []
    credentials = client.OAuth2Credentials.from_json(flask.session['credentials'])
    service = get_gcal_service(credentials)
    timeMin = flask.session["begin_date"]
    timeMax = flask.session["end_date"]

    for cal in flask.session['calendars']:
        if(cal['selected']==True):
            temp_id = cal["id"]
            #print("Found a selected cal")
            events = service.freebusy().query(body={"timeMin": timeMin , "timeMax": timeMax, "items": [{"id": temp_id }]}).execute()
            #print(events)
            for event in events['calendars'][temp_id]['busy']:
                #print(event)
                busy_list.append(event)
                temp_start = arrow.get(event["start"]).format("HH:mm:ss")
                temp_end = arrow.get(event["end"]).format("HH:mm:ss")
                busy_list_display.append({"start": temp_start , "end":temp_end })
    flask.session['busy_list'] = busy_list
    print(busy_list)
    #print(busy_list_display)
    flask.session['busy_list_display'] = busy_list_display

def createFreeList():
    """
    assumptions:
        user has pulled in calendars
        busy_list has been stored in session
    args:
        none
    returns:
        stores free list in session
    """

    free_list = []
    """
    """
    print("Made it to createFreeList")

    temp_start_date = arrow.get(flask.session['begin_date'])
    temp_start_min = arrow.get(flask.session['begin_time']).minute
    temp_start_hour = arrow.get(flask.session['begin_time']).hour
    temp_start = temp_start_date.replace(hour=temp_start_hour, minute=temp_start_min)
    temp_end_date = arrow.get(flask.session['end_date'])
    temp_end_min = arrow.get(flask.session['end_time']).minute
    temp_end_hour = arrow.get(flask.session['end_time']).hour
    temp_end = temp_end_date.replace(hour=temp_end_hour, minute=temp_end_min)
    print(temp_start.isoformat())
    print(temp_end.isoformat())
    #freeblock = agenda.Appt(temp_start,temp_end,"Freeblock")
    #print("Freeblock: " + freeblock)
    busy_Agenda = agenda.Agenda.from_list(flask.session['busy_list'])
    print("Completed")
    print(busy_Agenda)
    #free_list = busy_Agenda.complement(freeblock)

    #TODO: use busy list and complement to create free list

    flask.session['free_list'] = free_list
    print(free_list)

def checkEventRange(start, end):
    """
    assumptions:
        createBusyList has been called, thus only busy events are examined
        events end on the same day they are started
    args:
        start: arrow object representing a calendar event's start time
        end: arrow object representing a calendar event's end time
    return:
        true if in date/timerange
        false if not in date/timerange
    """
    #check if correct daterange
    if(end.date() < flask.session['begin_date']) or (start.date() > flask.session['end_date']):
        return False

    #check if correct timerange
    elif(end.time() < flask.session['meet_start_time']) or (start.time() > flask.session['meet_end_time']):
        return False

    #if in range:
    else:
        return True



def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict, so that
    it can be stored in the session object and converted to
    json for cookies. The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")  
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal: 
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]
        

        result.append(
          { "kind": kind,
            "id": id,
            "summary": summary,
            "selected": selected,
            "primary": primary
            })
    return sorted(result, key=cal_sort_key)


def cal_sort_key( cal ):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
       selected_key = " "
    else:
       selected_key = "X"
    if cal["primary"]:
       primary_key = " "
    else:
       primary_key = "X"
    return (primary_key, selected_key, cal["summary"])


#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"
    
#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running in a CGI script)

  app.secret_key = str(uuid.uuid4())  
  app.debug=CONFIG.DEBUG
  app.logger.setLevel(logging.DEBUG)
  # We run on localhost only if debugging,
  # otherwise accessible to world
  if CONFIG.DEBUG:
    # Reachable only from the same computer
    app.run(port=CONFIG.PORT)
  else:
    # Reachable from anywhere 
    app.run(port=CONFIG.PORT,host="0.0.0.0")
    
