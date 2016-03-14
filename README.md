David Chapman
CIS 399
University of Oregon Winter 2016
Meet Me Appointment Scheduler
========================================================================
Repo home: https://github.com/chapman3/proj6-Gcal
On ix: chapman3/public_html/cis399/htbin/proj6-Gcal
========================================================================
Goal of Project:
    User Flow:
        []Enter desired meeting information
            -description
            -location
            -daterange
            -timerange
            -duration
        []Connect to and access google calendars
        []display calendar options
        []select desired calendars
        []busy and available times populate screen
        []user confirms selection
        []page redirects user to an invitation link
        []user emails link to invitee
        []invitee follows link
        []server allows invitee to connect to google calendars
        []invitee selects calendars
        []busy and available times populate screen
        []user confirms selection
        []common available meeting times populate screen
        []invitee selects one, is provided with meeting information
            -emails back to original user
========================================================================
State of Project:

Currently the user can:
    []enter meeting information
    []connect to a calendar service
        -but not select individual calendars
    []busy times populate screen
        -not free times
    []confirm meeting details
        -redirects to response.html containing meeting details

As Well:
    []agenda.py fully operational
        -test case runs when run as main

Issues:
    []couldn't resolve freeblock into an agenda.Appt object
        -using begin_date and end_date in arrow format while replacing times with begin_time and start_time
            -results in a crash on redirect to '/busy'

========================================================================
This project is still a work in progress!