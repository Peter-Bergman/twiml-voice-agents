# twiml-voice-agents

# Minimal Usage

## Installing

Run `python3 -m pip install twiml-voice-agents`

## Setup

### Anthropic

Get an Anthropic API key.

Set the `ANTHROPIC_API_KEY` environment variable to your API key.

### Square

Get a Square OAuth Token with the following permissions:
...

Set the `SQUARE_ACCESS_TOKEN` environment variable to your OAuth token

### Ngrok

Get an ngrok token

Set the `NGROK_AUTHTOKEN` environment variable to your auth token

### Twilio Telephony

Set up a Twilio phone number to handle incoming calls with a TwiML webhook of your choice.
Set the webhook URL to the ngrok domain along with path `/call`.
Set the HTTP method to POST.

## Running Server

```python
import twiml_voice_agents as tva
srvr = tva.Server(tva.Conversation)
srvr.run()
```

## Using Agent, Finally

Lastly, call the Twilio phone number you configured.
