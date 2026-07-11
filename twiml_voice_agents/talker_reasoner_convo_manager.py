from abc import ABC, abstractmethod
from .abstract_convo_manager import AbstractConvoManager
import asyncio
from dataclasses import dataclass, field
from google import genai
import os
from typing import Awaitable, Callable, Dict, List, Self
from zoneinfo import ZoneInfo

types = genai.types

ToolList = List[Callable]

@dataclass
class TalkerConfig():
    system_instructions: str = None
    model: str = "gemini-3.1-flash-lite"
    tools: ToolList = field(default_factory=list)
    enable_forward_to_voicemail_tool: bool = False

class TalkerReasonerConvoManager(AbstractConvoManager):
    def __init__(
        self,
        ws_send_json,
        from_phone_number,
        forwarded_from_phone_number,
        talker_config: TalkerConfig = TalkerConfig(),
        initiate_convo = True,
        #TODO: add reasoners_config
    ):
        super().__init__(
            ws_send_json,
            from_phone_number,
            forwarded_from_phone_number
        )

        self.talker_config = talker_config
        talker_tools = talker_config.tools + ([self.forward_to_voicemail] if talker_config.enable_forward_to_voicemail_tool else [])
        self.genai_client = genai.Client()
        self.talker_chat = TalkerReasonerConvoManager.build_talker_chat(
            self.genai_client,
            talker_config.model,
            talker_config.system_instructions,
            talker_tools
        )

    async def handle_voice_prompt(
        self: Self,
        voice_prompt: str,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle voice prompt from caller and possibly respond
        """
        llm_response = self.talker_chat.send_message_stream(voice_prompt)

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

    async def handle_dtmf(
        self: Self,
        digit: str,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle dual-tone multi-frequency (touch-tone) input from caller
        """
        msg = f"You pressed {digit}. My apologies, I am not sure what to do with that."
        print(msg)
        return msg

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
        return None

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
        msg = f"Error message from WebSocket\n{msg_data}"
        print(msg)
        return msg

    @staticmethod
    def build_talker_chat(
        genai_client,
        model: str,
        system_instructions: str,
        tools: ToolList
    ):
        return genai_client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=system_instructions,
                thinking_config=types.ThinkingConfig(thinking_budget=0), # indicates "reasoning" not allowed before generating response
                tools=tools
            )
        )
