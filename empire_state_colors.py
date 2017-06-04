"""
This sample demonstrates a simple skill built with the Amazon Alexa Skills Kit.
The Intent Schema, Custom Slots, and Sample Utterances for this skill, as well
as testing instructions are located at http://amzn.to/1LzFrj6

For additional samples, visit the Alexa Skills Kit Getting Started guide at
http://amzn.to/1LGWsLG
"""

from __future__ import print_function
import datetime

from get_esb_schedule import get_schedule

APP_ID = 'amzn1.echo-sdk-ams.app.31643b52-4268-49fe-be40-89ecce49118d'
BAD_DATE = 'I didn\'t understand what date you asked for. Try asking for a specific date or day this week.'
HELP = 'Ask me about a date to learn the color of the Empire State Building.'
TITLE = 'Empire State Building Color'

def lambda_handler(event, context):
    if event['session']['application']['applicationId'] != APP_ID:
        raise ValueError('Invalid Application ID')

    request_type = event['request']['type']
    if request_type == 'LaunchRequest':
        return on_launch_request(event['request'])
    elif request_type == 'IntentRequest':
        return on_intent_request(event['request'])
    elif request_type == 'SessionEndedRequest':
        return
    else:
        return on_error(Exception('Unknown request type: ' + request_type))

def on_launch_request(request):
    return on_help_request()

def on_intent_request(request):
    intent_type = request['intent']['name']
    if intent_type == 'GetESBColor':
        return on_color_intent(request['intent'])
    elif intent_type == 'AMAZON.HelpIntent':
        return on_help_request()
    else:
        return on_error(Exception('Unknown intent type: ' + intent_type))

# --------------- Functions that control the skill's behavior ------------------

def on_error(exception):
    text = 'There was an error: ' + exception.message
    return build_simple_response(text)

def on_help_request():
    return build_simple_response(HELP)

def on_color_intent(intent):
    # Figure out what date the user wants:
    slots = intent['slots']
    if 'Date' in slots and 'value' in slots['Date']:
        date = parse_date(slots['Date']['value'])
        if not date:
            return build_simple_response(BAD_DATE)
    else:
        date = datetime.datetime.now()

    # What color is it??
    response = get_color_answer(date)
    return build_simple_response(response)

def parse_date(date_text):
    if date_text == '':
        return None

    if date_text == 'PRESENT_REF':
        now = datetime.datetime.now()
        return now - datetime.timedelta(days=(-1 if now.hour < 4 else 0))

    # TODO: Handle months / weeks
    try:
        return datetime.datetime.strptime(date_text, '%Y-%m-%d')
    except:
        print('Unexpected date: ' + date_text)
        return None

def get_color_answer(dt):
    return get_schedule().get_date_lighting(dt)


# --------------- Helpers that build all of the responses ----------------------

def build_simple_response(text):
    speechlet = build_speechlet_response(TITLE, text, None, True)
    return build_response({}, speechlet)

def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': 'SessionSpeechlet - ' + title,
            'content': 'SessionSpeechlet - ' + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }
