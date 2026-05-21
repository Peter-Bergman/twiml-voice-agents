from .agent import VirtualAgent
from claudette import *
from twilio.twiml.voice_response import Record
from typing import Self

class LLMAgent(VirtualAgent, Chat):
    non_replies_in_a_row: int = 0
    max_non_replies: int = 3

    def __init__(
        self: Self,
        from_num: str,
        forwarded_from_num: str | None,
        to_num: str,
        call_sid: str,
        system_prompt: str = "",
        hang_up_route: str = "/hang_up",
        model: str = "claude-haiku-4-5",
        *args,
        **kwargs
    ):
        super().__init__(
            sp=system_prompt,
            model=model,
            *args,
            **kwargs
        )
        self.hang_up_route = hang_up_route

    @VirtualAgent.timed
    def get_next_response(self: Self, user_input: str) -> str:
        """
        Runs tool loop and returns LLM's latest text response
        """
        llm_responses = self.toolloop(user_input)
        for llm_response in llm_responses:
            continue
            # print(f"llm_response ({type(llm_response)}): {llm_response}")

        agent_response = llm_responses.value[-1]["content"][0]["text"]
        agent_response = self.resolve_agent_response(agent_response)

        return agent_response

    @VirtualAgent.timed
    def handle_silence(self: Self) -> str | Record:
        self.non_replies_in_a_row += 1

        if self.non_replies_in_a_row >= 3:
            return Record(
                action=self.hang_up_route, # FIXME: fill in
                # method="", # FIXME: fill in
                max_length=60,
                finish_on_key="#" # TODO: maybe change to * key
            )
        elif self.h == []: # if no chat history yet
            return self.opening_line
        else:
            llm_responses = self.toolloop("[SILENCE]")
            for llm_response in llm_responses:
                continue
                # print(f"llm_response ({type(llm_response)}): {llm_response}")
            agent_response = llm_responses.value[-1]["content"][0]["text"]
            agent_response = self.resolve_agent_response(agent_response)
            return agent_response

    def resolve_agent_response(self: Self, agent_response: str) -> str | Record:
        if agent_response == "[VOICEMAIL]":
            return Record(
                action=self.hang_up_route,
                # method="", # FIXME: fill in
                max_length=60,
                finish_on_key="#" # TODO: maybe change to * key
            )
        else:
            return agent_response
