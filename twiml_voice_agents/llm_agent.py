from .agent import VirtualAgent
from claudette import *
from typing import Self

class LLMAgent(VirtualAgent, Chat):
    non_replies_in_a_row: int = 0
    max_non_replies: int = 3

    def __init__(self: Self, system_prompt: str = "", *args, **kwargs):
        super().__init__(
            sp=system_prompt,
            model="claude-haiku-4-5",
            *args,
            **kwargs
        )


    def get_next_response(self: Self, user_input: str) -> str:
        """
        Runs tool loop and returns LLM's latest text response
        """
        llm_responses = self.toolloop(user_input)
        for llm_response in llm_responses:
            continue
            # print(f"llm_response ({type(llm_response)}): {llm_response}")

        response_for_user = llm_responses.value[-1]["content"][0]["text"]
        return response_for_user

    def handle_silence(self: Self) -> str:
        self.non_replies_in_a_row += 1
        # if (self.non_replies_in_a_row >= self.self.max_non_replies):
        #     pass
        if self.h == []:
            return self.opening_line
        else:
            llm_responses = self.toolloop("[SILENCE]")
            for llm_response in llm_responses:
                continue
                # print(f"llm_response ({type(llm_response)}): {llm_response}")
            response_for_user = llm_responses.value[-1]["content"][0]["text"]
            return response_for_user
