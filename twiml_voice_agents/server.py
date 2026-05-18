# from agent import Conversation
from .agent import VirtualAgent
import asyncio
from fastapi import FastAPI, Form
from fastapi.responses import Response
import os
from pyngrok import ngrok
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, SsmlProsody
from typing import List, Self, Literal
import uvicorn

call_route = "/call"
respond_route = "/respond"
silence_route = "/handle_silence"

class Server(FastAPI):
    conversations: List[VirtualAgent] = {}
    language: str = "en-US"
    voice: str = "Man"
    speech_rate: str = "default"

    def __init__(
        self: Self,
        voice_agent_type: type[VirtualAgent],
        language: str | None = None,
        voice: str | None = None,
        speech_rate: str | None = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.language = language if language is not None else self.language
        self.voice = voice if voice is not None else self.voice
        self.speech_rate = speech_rate if speech_rate is not None else self.speech_rate

        app = self # sticking to naming conventions

        @app.post(call_route)
        async def call(From: str = Form(...), ForwardedFrom: str | None = Form(None), To: str = Form(...), CallSid: str = Form(...)):
            conversation = voice_agent_type(
                from_num=From,
                forwarded_from_num=ForwardedFrom,
                to_num=To,
                call_sid=CallSid
            )

            self.conversations[CallSid] = conversation

            response = VoiceResponse()

            gather = Gather(input="speech", language=self.language, action="/respond", method="POST")
            gather.say(language=self.language, voice=self.voice).prosody(conversation.opening_line, rate=self.speech_rate)

            response.append(gather)
            response.redirect(silence_route, method="POST")
            print(str(response))
            return Response(content=str(response), media_type="application/xml")

        @app.post(respond_route)
        async def respond(SpeechResult: str = Form(...), CallSid: str = Form(...)):
            print("SpeechResult:", SpeechResult)
            conversation: VirtualAgent = self.conversations[CallSid]
            response_text = conversation.get_next_response(SpeechResult)

            response = VoiceResponse()
            gather = Gather(input="speech", language=self.language, action="/respond", method="POST", speechTimeout="2", timeout="3")

            gather.say(language=self.language, voice=self.voice).prosody(response_text, rate=self.speech_rate)
            response.append(gather)
            response.redirect(silence_route, method="POST")
            print(str(response))
            return Response(content=str(response), media_type="application/xml")

        @app.post(silence_route)
        async def handle_silence(CallSid: str = Form(...)):
            conversation: VirtualAgent = self.conversations[CallSid]
            response_text = conversation.handle_silence()

            response = VoiceResponse()
            gather = Gather(input="speech", language=self.language, action="/respond", method="POST", speechTimeout="2", timeout="3")

            gather.say(language=self.language, voice=self.voice).prosody(response_text, rate=self.speech_rate)
            response.append(gather)
            response.redirect(silence_route, method="POST")
            print(str(response))
            return Response(content=str(response), media_type="application/xml")


    async def run_async(self: Self):
        ngrok.set_auth_token(os.getenv("NGROK_AUTHTOKEN"))
        public_url = ngrok.connect(8000)
        print(f"Public URL: {public_url}")

        config = uvicorn.Config(self, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    def run(self: Self):
        asyncio.run(self.run_async())


if __name__ == "__main__":
    from conversation import Conversation
    server = Server(Conversation)
    server.run()
