import asyncio
from datetime import datetime, timezone
from google import genai
import os
from typing import Awaitable, Callable, Dict, List, Optional, Self
from zoneinfo import ZoneInfo


types = genai.types

class Talker():
    client = genai.Client()

    def __init__(
        self: Self,
        ws_send_json: Callable[[Dict], Awaitable[None]],
        from_phone_number: str,
        model: str,
        system_prompt: str,
        tools: List[callable] = []
    ):
        self.ws_send_json = ws_send_json
        self.client = genai.Client()
        self.from_phone_number = from_phone_number
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools

        self.chat: genai.chats.Chat = Talker.build_chat_from_client(self.client, self.model, self.tools, self.system_prompt)

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

            llm_response = self.chat.send_message_stream(voice_prompt)

            for chunk in llm_response:
                if (chunk.text is not None) and (chunk.text != ""):
                    await self.send_msg_chunk_to_caller(chunk.text, False)
                elif chunk.text == "":
                    print("Received empty text chunk from LLM, skipping sending to caller")
                else:
                    print("Received chunk with no text content from LLM, skipping sending to caller")
                    print("Chunk", chunk)
            else:
                await self.send_msg_chunk_to_caller("", True)
            return None
            return_msg = llm_response.text
        elif msg_type == "dtmf":
            digit = msg_data.get("digit")
            return_msg = f"You pressed {digit}. My apologies, I am not sure what to do with that."
        elif msg_type == "interrupt":
            return_msg = None
        elif msg_type == "error":
            return_msg = "Uh-oh, there was an error."
        else:
            print("msg_type unrecognized")
            return_msg = None

        print("return_msg", return_msg)
        return return_msg

    async def send_msg_chunk_to_caller(self: Self, msg_chunk: str, is_last: bool):
        agent_response_data = {
            "type": "text",
            "token": msg_chunk,
            "last": is_last,
            "interruptible": True,
            "preemptible": False
        }
        await self.ws_send_json(agent_response_data)

    def mk_user_text_msg(self: Self, text: str) -> genai.types.ContentDict:
        return {
            "role": "user",
            "parts": [{
                "text": text
            }]
        }

    @staticmethod
    def build_chat_from_client(
        client: genai.Client,
        model: str,
        tools: List[callable],
        system_prompt: str,
    ) -> genai.chats.Chat:
        return client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                thinking_config=types.ThinkingConfig(thinking_budget=0), # indicates "reasoning" not allowed before generating response
                tools=tools
            )
        )

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

    def forward_to_voicemail(self: Self, reason: Optional[str] = None):
        """
        Args:
            reason: an optional reason given by the caller for why they are calling

        Returns:
            a str "forwarding to voicemail...", as long as no exception thrown
        """
        message = "forwarding to voicemail..."
        print(message)
        print("reason", reason)

        end_session_message = {
            "type": "end",
            "handoffData": "{\"reasonCode\":\"forward-to-voicemail\"}"
        }

        task = asyncio.get_event_loop().create_task( self.ws_send_json(end_session_message) )
        print("task", task)

        return message
