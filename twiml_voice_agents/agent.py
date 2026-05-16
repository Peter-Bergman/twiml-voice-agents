from abc import ABC, abstractmethod
from typing import Self

class VirtualAgent(ABC):

    def __init__(self: Self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    @abstractmethod
    def opening_line(self: Self) -> str:
        """
        Greeting and/or prompt for caller
        Not included in chat history
        Only intended to help caller start conversation with agent

        This exists because both Anthropic and OpenAI APIs expect "user" messages to precede any "assistant" (agent) messages
        """
        ...

    @abstractmethod
    def get_next_response(self: Self, user_input: str) -> str:
        ...

    @abstractmethod
    def handle_silence(self: Self) -> str:
        """
        Used to handle occasions where users do not respond/reply for a period of time
        """
        ...
