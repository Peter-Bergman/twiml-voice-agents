from abc import ABC, abstractmethod
from .abstract_convo_manager import AbstractConvoManager
import asyncio
from dataclasses import dataclass, field
from google import genai
from google.genai import types
import inspect
import os
from typing import Awaitable, Callable, Dict, List, Optional, Self
from zoneinfo import ZoneInfo

in_debug_mode = os.getenv("TVA_DEBUG") == "1"

ToolList = List[Callable]

@dataclass
class TalkerConfig():
    system_instructions: str = None
    model: str = "gemini-3.1-flash-lite"
    #TODO: maybe rename `tools` to indicate it is just a subset of tools and does not include telephony tools
    tools: ToolList = field(default_factory=list)
    enable_forward_to_voicemail_tool: bool = False

class TalkerReasonerConvoManager(AbstractConvoManager):
    def __init__(
        self: Self,
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

        self.talker_history: List[types.Content] = []
        self.last_part_type: Optional[str] = None
        self.lock = asyncio.Lock()
        self.streaming_task: Optional[asyncio.Task] = None
        #NOTE: the `self.streaming_task` has exclusive access to create `self.function_calling_task`
        self.function_calling_task: Optional[asyncio.Task] = None

        self.talker_config = talker_config
        self.talker_tools = talker_config.tools + ([self.forward_to_voicemail] if talker_config.enable_forward_to_voicemail_tool else [])
        print(f"Talker tools: {self.talker_tools}")
        self.genai_client = genai.Client()

    def add_assistant_part_to_talker_history(self: Self, part: types.Part) -> None:
        """
        Add part to talker history
        """
        is_last_part_assistant = self.talker_history and self.talker_history[-1].role == "assistant"
        if not is_last_part_assistant:
            self.talker_history.append( types.Content(role="assistant", parts=[]) )
            self.last_part_type = None

        if part.function_call:
            #NOTE: this code expects streamed function calls to be disabled
            self.talker_history[-1].parts.append(part)
            self.last_part_type = "function_call"
        elif part.text is not None and self.last_part_type == "text": # non-first consecutive text part
            self.talker_history[-1].parts[-1].text += part.text
            self.last_part_type = "text"
        elif part.text is not None: # first consecutive text part
            self.talker_history[-1].parts.append(part)
            self.last_part_type = "text"
        else:
            self.talker_history[-1].parts.append(part)
            self.last_part_type = "other"

    def add_user_part_to_talker_history(self: Self, part: types.Part) -> None:
        self.last_part_type = None
        self.talker_history.append( types.Content(role="user", parts=[part]) )

    async def stream_talker_response_to_caller(self: Self) -> None:
        """
        Stream response from talker to caller
        """
        try:
            llm_response = await self.genai_client.aio.models.generate_content_stream(
                model=self.talker_config.model,
                contents=self.talker_history,
                config=types.GenerateContentConfig(
                    system_instruction=self.talker_config.system_instructions,
                    thinking_config=types.ThinkingConfig(thinking_budget=0), # indicates "reasoning" not allowed before generating response
                    tools=self.talker_tools,
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode=types.FunctionCallingConfigMode.AUTO,
                            # stream_function_call_arguments=True
                        )
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )
            )

            async for chunk in llm_response:
                candidate = chunk.candidates[0]
                for part in candidate.content.parts:
                    # Check for the tool call here
                    if part.function_call:
                        self.function_calling_task = asyncio.create_task( self.dispatch_function_call(part) )

                        # breaking because function call already added (and hopefully function response via dispatch_function_call)
                        # function call should trigger talking again after completion (else, user voicePrompt will trigger talking after cancelling function call)
                        break

                    elif (part.text is not None) and (part.text != ""):
                        await self.send_msg_chunk_to_caller(part.text, False)
                    elif part.text == "":
                        print("Received empty text part from LLM, skipping sending to caller")
                    else:
                        print("Received part from LLM with no text content nor function call, skipping sending to caller")
                        print("Part", part)

                    self.add_assistant_part_to_talker_history(part)
            else:
                await self.send_msg_chunk_to_caller("", True)

            print(f"Full agent response: {self.talker_history[-1]}")
        except asyncio.CancelledError as cancelledError:
            if in_debug_mode == "1": breakpoint()
            print(cancelledError)
            raise
        except Exception as e:
            if in_debug_mode == "1": breakpoint()
            print(e)
            raise

    async def dispatch_function_call(self: Self, function_call_part: types.Part) -> None:
        """
        Dispatch function call to appropriate tool
        """
        assert function_call_part.function_call, "Part is not a function_call part"
        #NOTE: line below assumes function name is unique and exists in self.talker_tools
        function_name: str = function_call_part.function_call.name
        function_arguments: dict = function_call_part.function_call.args
        function_call_id: Optional[str] = function_call_part.function_call.id

        print(f"Function name: {function_name}")
        print(f"Function arguments: {function_arguments}")

        # add function call to talker history
        self.add_assistant_part_to_talker_history(function_call_part)

        try:
            # look up function to dispatch
            function_to_call = [ tool for tool in self.talker_tools if tool.__name__ == function_name ][0]
            if inspect.iscoroutinefunction(function_to_call):
                result = await function_to_call(**function_arguments)
            else:
                result = function_to_call(**function_arguments)
        except asyncio.CancelledError as cancelledError:
            if in_debug_mode == "1": breakpoint()
            # log cancellation message if exists
            if cancelledError.args: print(cancelledError)
            self.add_function_response_to_talker_history(function_name, {"error": "Cancelled/Interrupted"}, function_call_id)
            # need empty assistant speech between function response and user speech
            self.add_assistant_part_to_talker_history(part=types.Part(text=""))
            raise

        # add function response to talker history
        self.add_function_response_to_talker_history(function_name, {"result": result}, function_call_id)

        async with self.lock:
            # wait for streaming task to finish cleaning up, if needed
            if self.streaming_task is not None: await self.streaming_task
            self.streaming_task = asyncio.create_task( self.stream_talker_response_to_caller() )

        return

    def add_function_response_to_talker_history(self: Self, function_name: str, response: dict, function_call_id: Optional[str]) -> None:
        """
        Add function result to talker history
        """
        part = types.Part(
            function_response=types.FunctionResponse(
                id=function_call_id,
                name=function_name,
                response=response
            )
        )

        self.add_user_part_to_talker_history(part)

    async def handle_voice_prompt(
        self: Self,
        voice_prompt: str,
        msg_data: dict # non-setup message data, see https://www.twilio.com/docs/voice/conversationrelay/websocket-messages#getting-messages-from-twilio
    ) -> str | None:
        """
        Handle voice prompt from caller and possibly respond
        """
        async with self.lock:
            #TODO: maybe swap ordering
            await self.cancel_function_call()
            await self.cancel_streaming_task()

            self.add_user_part_to_talker_history( types.Part(text=voice_prompt) )
            self.streaming_task = asyncio.create_task( self.stream_talker_response_to_caller() )

        return None

    async def cancel_function_call(self: Self, log_msg_if_no_function_call: Optional[str] = None):
        """
        Cancels `self.function_calling_task` and optionally logs message if it does not exist
        """
        if self.function_calling_task is not None:
            self.function_calling_task.cancel()
            try:
                await self.function_calling_task
            except asyncio.CancelledError:
                if in_debug_mode == "1": breakpoint()
                print("Function calling task cancelled due to interruption from caller")
            self.function_calling_task = None
        elif log_msg_if_no_function_call:
            print(log_msg_if_no_function_call)

    async def cancel_streaming_task(self: Self, log_message_if_no_streaming_task: Optional[str] = None):
        if self.streaming_task is not None:
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                if in_debug_mode == "1": breakpoint()
                print("Streaming task cancelled due to interruption from caller")
            self.streaming_task = None
        elif log_message_if_no_streaming_task:
            print(log_message_if_no_streaming_task)

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
        print("Received interrupt message from caller")
        print(f"utteranceUntilInterrupt: {utteranceUntilInterrupt}")
        print(f"durationUntilInterruptMs: {durationUntilInterruptMs}")
        async with self.lock:
            await self.cancel_streaming_task("INFO: Received interrupt message, but no streaming task was active.")

            indexed_parts_in_last_response = enumerate(self.talker_history[-1].parts)
            indexed_text_parts_in_last_response = [ (index, part) for index, part in indexed_parts_in_last_response if part.text ]

            if indexed_text_parts_in_last_response:
                last_text_part_index, last_pretrimmed_text_part = indexed_text_parts_in_last_response[-1]
                print(f"Pre-trimmed text: {last_pretrimmed_text_part.text}")
                #WARNING: the empty str on the next line should possibly be `self.talker_history[-1].parts[last_text_part_index].text`
                self.talker_history[-1].parts[last_text_part_index].text = last_pretrimmed_text_part.text.rsplit(utteranceUntilInterrupt, 1)[0] if utteranceUntilInterrupt else ""
                print(f"Trimmed text: {self.talker_history[-1].parts[last_text_part_index].text}")
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
