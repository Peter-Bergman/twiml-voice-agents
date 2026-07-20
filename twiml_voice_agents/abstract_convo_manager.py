from abc import ABC, abstractmethod
import asyncio
import datetime
import os
from typing import Awaitable, Callable, Dict, Optional, Self
from zoneinfo import ZoneInfo

class AbstractConvoManager(ABC):

    from_phone_number: str
    forwarded_from_phone_number: str

    def __init__(
        self: Self,
        ws_send_json: Callable[[Dict], Awaitable[None]],
        from_phone_number: str,
        forwarded_from_phone_number: str
    ):
        self.ws_send_json = ws_send_json
        self.from_phone_number = from_phone_number
        self.forwarded_from_phone_number = forwarded_from_phone_number

    async def send_msg_chunk_to_caller(self: Self, msg_chunk: str, is_last: bool, interruptible: bool = True, preemptible: bool = False):
        agent_response_data = {
            "type": "text",
            "token": msg_chunk,
            "last": is_last,
            "interruptible": interruptible,
            "preemptible": preemptible
        }
        await self.ws_send_json(agent_response_data)

    async def handle_msg(
        self: Self,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None: # a str with plain text response agent should say, otherwise `None` for no response
        """
        Handle non-setup message data from Twilio <ConversationRelay> WebSocket and possibly respond
        """
        msg_type = msg_data.get("type")
        if msg_type == "prompt":
            voice_prompt: str = msg_data.get("voicePrompt")

            return_msg = await self.handle_voice_prompt(voice_prompt, msg_data)
        elif msg_type == "dtmf":
            digit = msg_data.get("digit")
            return_msg = await self.handle_dtmf(digit, msg_data)
        elif msg_type == "interrupt":
            utteranceUntilInterrupt = msg_data.get("utteranceUntilInterrupt")
            durationUntilInterruptMs = msg_data.get("durationUntilInterruptMs")
            return_msg = await self.handle_interrupt(utteranceUntilInterrupt, durationUntilInterruptMs, msg_data)
        elif msg_type == "error":
            description = msg_data.get("description")
            return_msg = await self.handle_error_msg(description, msg_data)
        else:
            #TODO: add a "louder" alert
            print("msg_type unrecognized")
            return_msg = None

        print("return_msg", return_msg)
        return return_msg

    @abstractmethod
    async def handle_voice_prompt(
        self: Self,
        voice_prompt: str,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle voice prompt from caller and possibly respond
        """
        ...

    @abstractmethod
    async def handle_dtmf(
        self: Self,
        digit: str,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle dual-tone multi-frequency (touch-tone) input from caller
        """
        ...

    @abstractmethod
    async def handle_interrupt(
        self: Self,
        utteranceUntilInterrupt: str,
        durationUntilInterruptMs: int,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle interruption from caller

        Per Twilio docs,
        > Conversation Relay sends this message when the caller interrupts TTS playback by speaking.
        """
        ...

    @abstractmethod
    async def handle_error_msg(
        self: Self,
        description: str,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle error from Twilio

        Per Twilio docs,
        > Conversation Relay sends this message when an error occurs during the session.
        """
        ...

    @staticmethod
    def get_override_call_handler_url(forwarded_from_phone_number: str) -> Optional[str]:
        """
        Used to determine if a call should be handled by a different server

        Returns:
            a URL str indicating where to Redirect (uses TwiML verb) callers, if a special handler is needed
            None if a call should be handled normally
        """
        return None

    @staticmethod
    def get_current_time(
        tz_db_id: str = os.getenv("TZ", "America/Chicago") # timezone database identifier
    ) -> str:
        """
        Get the current time in a more human-readable format.
        """

        tz = ZoneInfo(tz_db_id)

        now = datetime.now(tz) # Get current time in local timezone
        current_time = now.strftime("%I:%M:%S %p %Z")  # Using 12-hour format with AM/PM
        current_date = now.strftime(
            "%A, %B %d, %Y"
        ) # Full weekday, month name, day, and year

        return f"Current Date and Time = {current_date}, {current_time}"

    def forward_to_voicemail(self: Self):
        """
        Returns:
            a str "forwarding to voicemail...", as long as no exception thrown
        """
        message = "forwarding to voicemail..."
        print(message)

        end_session_message = {
            "type": "end",
            "handoffData": "{\"reasonCode\":\"forward-to-voicemail\"}"
        }

        task = asyncio.get_event_loop().create_task( self.ws_send_json(end_session_message) )
        print("task", task)

        return message
