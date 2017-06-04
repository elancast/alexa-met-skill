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
BAD_DATE = 'I didn\'t understand what date you asked for. Try asking for a specific date or month.'
HELP = 'To learn about ongoing Met Exhibits, ask me about the next exhibits or the next exhibits after a date'
TITLE = 'Met Exhibits'

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
    return on_help_intent()

def on_intent_request(request):
    intent_type = request['intent']['name']
    if intent_type == 'GetNextExhibits':
        return on_exhibits_intent(request['intent'])
    elif intent_type == 'AMAZON.HelpIntent':
        return on_help_intent()
    else:
        return on_error(Exception('Unknown intent type: ' + intent_type))


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Alexa <-> Custom logic - this handles converting between speech and logic
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

def on_exhibits_intent(intent):
  slots = intent['slots']
  if 'Date' in slots and 'value' in slots['Date']:
    date = parse_date(slots['Date']['value'])
    if not date:
      return build_simple_response(BAD_DATE)
    return build_listings_response(get_exhibits_ending_after_date(date), date)
  else:
    return build_listings_response(get_next_ending_exhibits())

def on_help_intent():
  return build_simple_response(HELP)

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

    # This year
    if not '-' in date_text:
      return one_day_ago

    # TODO: Handle months / weeks
    try:
      fmt = '%Y-%m-%d' if date_text.count('-') > 1 else '%Y-%m'
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


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Business logic! This part handles all the high level queries
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
LIMIT = 3

def get_next_ending_exhibits():
  return _get_sorted_exhibit_listings()[:LIMIT]

def get_exhibits_ending_after_date(date):
  exhibits = filter(
    lambda x: x.get_through_date() >= date,
    _get_sorted_exhibit_listings()
    )
  return exhibits[:LIMIT]

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
