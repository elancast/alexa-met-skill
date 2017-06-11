"""
This is a lambda function for the Amazon Alexa thing to provide users with
information about what current Met exhibits are available.
"""

import datetime
import json
import urllib2


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Lambda API handlers
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

APP_ID = 'amzn1.ask.skill.31de1985-df73-45f5-bb6a-22a5c62b2c43'
BAD_DATE_OUTPUT = 'I didn\'t understand what date you asked for. Try asking for a specific date or month.'
DATE_SLOT_NAME = 'Date'
INTENT_NAME = 'GetNextExhibits'
LAUNCH_OUTPUT = ''
LAUNCH_REPROMPT = 'What date would you like to know about Met exhibits after?'
HELP_OUTPUT = 'Met Exhibits tells you the special exhibitions at the Metropolitan Museum of Art that are ending soon. To try it, ask me about the next exhibits or the next exhibits ending after a date.'
HELP_REPROMPT = 'When would you like to know about exhibits ending after?'
TITLE = 'Met Exhibits'

BAD_DATE_REPROMPT = LAUNCH_REPROMPT

def lambda_handler(event, context):
    print('here in lambda handler')
    print(json.dumps(event))
    if event['session']['application']['applicationId'] != APP_ID:
        raise ValueError('Invalid Application ID')

    request_type = event['request']['type']
    if request_type == 'LaunchRequest':
        return on_launch_request(event['request'])
    elif request_type == 'IntentRequest':
        return on_intent_request(event['request'], event['session']['new'])
    elif request_type == 'SessionEndedRequest':
        return
    else:
        return on_error(Exception('Unknown request type: ' + request_type))

def on_launch_request(request):
    return on_launch_intent()

def on_intent_request(request, is_new_session):
    intent_type = request['intent']['name']
    if intent_type == INTENT_NAME:
        return on_exhibits_intent(request['intent'], is_new_session)
    elif intent_type == 'AMAZON.HelpIntent':
        return on_help_intent()
    elif intent_type == 'AMAZON.StopIntent':
        return build_simple_response('Okay.')
    else:
        return on_error(Exception('Unknown intent type: ' + intent_type))


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Alexa <-> Custom logic - this handles converting between speech and logic
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

def on_exhibits_intent(intent, is_new_session):
  slots = intent['slots']
  has_date = DATE_SLOT_NAME in slots and 'value' in slots[DATE_SLOT_NAME]
  if has_date:
    date = parse_date(slots[DATE_SLOT_NAME]['value'])
    if not date:
      return on_bad_date()
    return build_listings_response(get_exhibits_ending_after_date(date), date)
  elif not is_new_session and not has_date:
    return on_bad_date()
  else:
    return build_listings_response(get_next_ending_exhibits())

def on_bad_date():
  return build_open_response(BAD_DATE_OUTPUT, BAD_DATE_REPROMPT)

def on_help_intent():
  return build_open_response(HELP_OUTPUT, HELP_REPROMPT)

def on_launch_intent():
  return build_open_response(LAUNCH_OUTPUT, LAUNCH_REPROMPT)

def on_error(exc):
  text = 'There was an error: ' + exc.message
  return build_simple_response(text)

def parse_date(date_text):
    if date_text == '':
      return None

    now = datetime.datetime.now()
    one_day_ago = now - datetime.timedelta(days=-1)
    if date_text == 'PRESENT_REF':
      return one_day_ago

    # Asking about this month returns next year
    this_month_bug = '%d-%s' % (now.year + 1, now.strftime('%m'))
    if date_text == this_month_bug:
      return one_day_ago

    fmt = '%Y'
    if date_text.count('-') == 1:
      fmt = '%Y-%m'
    elif date_text.count('-') == 2:
      fmt = '%Y-%m-%d'

    try:
      return datetime.datetime.strptime(date_text, fmt)
    except:
      print('Unexpected date: ' + date_text)
      return None

def build_listings_response(listings, date=None):
  if len(listings) == 0:
    text = 'Sorry, there are no ongoing Met exhibits after that date.'
    return build_simple_response(text)

  listings_texts = map(lambda x: x.to_alexa_text(), listings)
  if len(listings_texts) > 1:
    listings_texts.insert(len(listings_texts) - 1, 'and')

  text = 'The next ending exhibits are %s' % ', '.join(listings_texts)
  return build_simple_response(text)

def build_simple_response(text):
  speechlet = build_speechlet_response(TITLE, text)
  return build_response({}, speechlet)

def build_open_response(output_text, reprompt_text):
  return build_response(
    {},
    {
        'outputSpeech': {
             'type': 'PlainText',
             'text': output_text + ' ' + reprompt_text
             },
        'card': {
          'type': 'Simple',
          'title': 'SessionSpeechlet',
          'content': 'SessionSpeechlet'
          },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
                }
            },
        'shouldEndSession': False
        }
    )

def build_speechlet_response(title, output):
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
        'text': None
        }
      },
    'shouldEndSession': True
    }

def build_response(session_attributes, speechlet_response):
  return {
    'version': '1.0',
    'sessionAttributes': session_attributes,
    'response': speechlet_response
    }


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Business logic! This part handles all the high level queries
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
LIMIT = 3

def get_next_ending_exhibits():
  return _take_limit(_get_sorted_exhibit_listings())

def get_exhibits_ending_after_date(date):
  exhibits = filter(
    lambda x: x.get_through_date() >= date,
    _get_sorted_exhibit_listings()
    )
  return _take_limit(exhibits)

def _take_limit(exhibits):
  desired = exhibits[:LIMIT]
  last = desired[-1]

  # Add on any that end on the same date (so we don't lose them in limit)
  i = LIMIT
  while i < len(exhibits) and \
        exhibits[i].get_through_date() == last.get_through_date():
    desired.append(exhibits[i])
    i += 1

  return desired

def _get_sorted_exhibit_listings():
  return sorted(
    get_current_listings(),
    key=lambda listing: listing.get_through_date()
    )

""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Objects for understanding the Met API
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
END_DATE_FMT = 'Through %B %d, %Y'
class MetExhibitListing:
  def __init__(self, json_object):
    self._title = json_object['title']

    # Parse when the exhibit expires
    through_text = json_object['meta1']
    if not ', ' in through_text:
      through_text += ', %d' % (datetime.datetime.now().year)
    self._through = datetime.datetime.strptime(through_text, END_DATE_FMT)
    self._through_text = through_text.replace('Through ', '')

  def get_through_date(self):
    return self._through

  def to_alexa_text(self):
    through_text = self._through_text
    title = self._title.lower()

    # Remove the year
    if ',' in through_text:
      comma = through_text.index(',')
      through_text = through_text[:comma]

    # Remove any text in parens
    while '(' in title:
      start = title.index('(')
      end = title.index(')', start + 1)
      title = title[:start] + ' ' + title[end + 1:]

    # Remove any tags!
    while '<' in title:
      start = title.index('<')
      end = title.index('>', start + 1)
      title = title[:start] + ' ' + title[end + 1:]

    # Remove some common wordy titles
    title = title.replace('selections from', ' ')
    title = title.replace('.', ' ')

    # Here we go!
    return '%s ending on %s' % (title, through_text)


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Calling the Met API and converting it into Objects
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
MET_LISTINGS_PAGE = 'http://www.metmuseum.org/api/Exhibitions/CurrentExhibitionsListing?location=main%7Cbreuer%7Ccloisters&null=&page=1'

_CACHED_LISTINGS = None
def get_current_listings():
  global _CACHED_LISTINGS
  if _CACHED_LISTINGS == None:
    _CACHED_LISTINGS = _get_current_listings()
  return _CACHED_LISTINGS

def _get_current_listings():
  resp = urllib2.urlopen(MET_LISTINGS_PAGE)
  s = resp.read()
  resp.close()
  return map(
    lambda x: MetExhibitListing(x),
    json.loads(s)['results']
    )


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# For debugging
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

if __name__ == '__main__':
  import pdb; pdb.set_trace()
