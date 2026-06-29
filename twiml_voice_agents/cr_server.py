from .agent import VirtualAgent
from .talker import Talker
import asyncio
from fastapi import FastAPI, Form, Response, WebSocket, Request
import json
import os
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, ConversationRelay, VoiceResponse
from typing import Dict, Optional, Self, Callable, List
from urllib.parse import parse_qs
import uvicorn

domain = os.getenv("DOMAIN")  # e.g. "abc123.io"
assert domain is not None, "DOMAIN env var required, but missing"
twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
assert twilio_auth_token is not None, "TWILIO_AUTH_TOKEN env var required, but missing"
use_ngrok = os.getenv("USE_NGROK", "").lower() in ("1", "t", "true", "y", "yes")
print("use_ngrok", use_ngrok)

call_route = "/call"
ws_route = "/connect_action"
on_conversation_relay_end_route = "/on_conversation_relay_ended"
hang_up_route = "/hang_up"

#TODO: replace print calls with logging

class ConversationRelayServer(FastAPI):

    # Initialize the request validator
    twilio_signature_validator = RequestValidator(twilio_auth_token)

    def __init__(
        self,
        voice_agent_type: type[Talker],
        load_sys_instr: Callable[[str], str], # maps forwarded from phone number to client system instructions
        model: str = "gemini-2.5-flash",
        #TODO: use params below
        language: str | None = None,
        voice: str | None = None,
        speech_rate: str | None = None,
        *args,
        **kwargs
    ):
        self.model = model
        self.language = language
        self.voice = voice
        self.speech_rate = speech_rate
        self.load_sys_instr = load_sys_instr
        super().__init__(*args, **kwargs)

        app = self # sticking to naming conventions

        @app.post(call_route)
        async def call(From: str = Form(...), ForwardedFrom: str | None = Form(None), To: str = Form(...), CallSid: str = Form(...)):

            response = VoiceResponse()
            connect = Connect(action=f"https://{domain}{on_conversation_relay_end_route}")
            connect.conversation_relay(
                url=f"wss://{domain}{ws_route}",
            )
            response.append(connect)

            print(response)
            return Response(str(response), media_type="application/xml")

        @app.websocket(ws_route)
        async def connect_action(websocket: WebSocket):
            print("ws headers", websocket.headers)
            signature = websocket.headers.get("X-Twilio-Signature")
            is_signature_legit = self.verify_twilio_signature(str(websocket.url), {}, signature)
            assert is_signature_legit, "Invalid Signature in X-Twilio-Signature HTTP header when opening WebSocket connection"
            await websocket.accept()
            setup_msg = await websocket.receive_text()
            setup_data = json.loads(setup_msg)
            print("setup_data", setup_data)
            call_sid = setup_data.get("callSid")
            forwarded_from_phone_number = setup_data.get("forwardedFrom")

            system_instructions = self.load_sys_instr(forwarded_from_phone_number)

            #TODO: maybe make talker contextual var
            talker: Talker = voice_agent_type(websocket.send_json, forwarded_from_phone_number, model=self.model, system_prompt=system_instructions)

            # HACK: I would like to not have to encode fake Twilio data
            await talker.handle_msg({"type": "prompt", "voicePrompt":""})

            while True:
                #TODO: maybe replace with receive_json
                msg = await websocket.receive_text()
                msg_data = json.loads(msg)
                print("msg_data", msg_data)
                await talker.handle_msg(msg_data)

        @app.post(on_conversation_relay_end_route)
        async def on_conversation_relay_end(request: Request):
            request_body = await request.form()
            print("request_body", request_body)
            handoff_data: Optional[str] = request_body.get("HandoffData")
            session_status: str = request_body.get("SessionStatus")
            parsed_handoff_data: dict = json.loads(handoff_data) if handoff_data else {}
            handoff_reason_code = parsed_handoff_data.get("reasonCode")
            voice_response = VoiceResponse()
            if handoff_reason_code == "forward-to-voicemail" and session_status == "ended":
                voice_response.record(
                    action=hang_up_route,
                    max_length=60,
                    finish_on_key="#"
                )
            elif handoff_reason_code == "hang-up" and session_status == "ended":
                voice_response.hangup()
            elif session_status == "completed":
                print("Caller hung up")
            elif session_status == "failed":
                print("Something went wrong with the WebSocket connection.")
                print("request_body", request_body)
            else:
                print("ConversationRelay session ended for unknown reason")
                print("request_body", request_body)
            return Response(str(voice_response), media_type="application/xml")

        @app.post(hang_up_route)
        async def hang_up(CallSid: str = Form(...)):
            response = VoiceResponse()
            response.hangup()
            return Response(content=str(response), media_type="application/xml")

    async def run_async(self: Self):
        if use_ngrok:
            from pyngrok import ngrok
            ngrok_auth_token = os.getenv("NGROK_AUTHTOKEN")

            ngrok.set_auth_token(ngrok_auth_token)
            public_url = ngrok.connect(8000)
            print(f"Public URL: {public_url}")

        #TODO: make host and port configurable
        config = uvicorn.Config(self, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    def run(self: Self):
        asyncio.run(self.run_async())

    def verify_twilio_signature(self: Self, url: str, params: dict, signature: str) -> bool:
        print("signature", signature)
        print("url", url)
        url = url.replace("ws://", "wss://") # for handling requests forwarded from CloudFront
        return self.twilio_signature_validator.validate(url, params, signature)
