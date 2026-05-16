# from agent import Conversation
from .agent import VirtualAgent
import asyncio
from fastapi import FastAPI, Form
from fastapi.responses import Response
import os
from pyngrok import ngrok
from twilio.twiml.voice_response import VoiceResponse, Gather
from typing import List, Self
import uvicorn

class Server(FastAPI):
    conversations: List[VirtualAgent] = {}

    def __init__(self: Self, voice_agent_type: type[VirtualAgent], *args, **kwargs):
        super().__init__(*args, **kwargs)

        app = self # sticking to naming conventions

        @app.post("/call")
        async def call(From: str = Form(...), ForwardedFrom: str | None = Form(None), To: str = Form(...), CallSid: str = Form(...)):
            conversation = voice_agent_type(
                from_num=From,
                forwarded_from_num=ForwardedFrom,
                to_num=To,
                call_sid=CallSid
            )

            self.conversations[CallSid] = conversation

            response = VoiceResponse()
            gather = Gather(input="speech", action="/respond", method="POST")
            gather.say(conversation.opening_line)
            response.append(gather)
            print(str(response))
            return Response(content=str(response), media_type="application/xml")

        @app.post("/respond")
        async def respond(SpeechResult: str = Form(...), CallSid: str = Form(...)):
            print("SpeechResult:", SpeechResult)
            conversation: VirtualAgent = self.conversations[CallSid]
            response_text = conversation.get_next_response(SpeechResult)

            response = VoiceResponse()
            gather = Gather(input="speech", action="/respond", method="POST", speechTimeout="2", timeout="3")

            gather.say(response_text)
            response.append(gather)
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
