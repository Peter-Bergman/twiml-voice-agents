# twiml-voice-agents

# Why Use twiml-voice-agents

Configuring an agent is fairly simple and easy.

# Limitations

The twiml-voice-agents package is limited by the fact that it supports half-duplex communication.

Half-duplex means that both a caller and the agent can speak, but only one at a time.
The caller can interrupt the agent (technical name for this is *barge-in*).
However, due to the nature of TwiML apps, there is a time when caller input will be lost.
That period begins when Twilio detects an end-of-turn for the caller and awaits a response from your twiml-voice-agents server.

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
srvr = tva.Server(tva.SquareSchedulingAgent)
srvr.run()
```

## Taling to Agent, Finally

Lastly, call the Twilio phone number you configured.
