from abc import ABC, abstractmethod
import time
from typing import Self
from twilio.twiml import TwiML

class VirtualAgent(ABC):

    def __init__(self: Self, verbose: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def timed(func: function):
        def wrapper(self, *args, **kwargs):
            start = time.perf_counter()
            result = func(self, *args, **kwargs)
            elapsed = time.perf_counter() - start
            print(f"{func.__qualname__} took {elapsed:.3f}s")
            return result
        return wrapper

    @property
    @abstractmethod
    def opening_line(self: Self) -> str:
        """
        Greeting and/or prompt for caller
        Intended to help caller start conversation with agent

        This exists because both Anthropic and OpenAI APIs expect "user" messages to precede any "assistant" (agent) messages
        """
        ...

    @abstractmethod
    def get_next_response(self: Self, user_input: str) -> str | TwiML:
        ...

    @abstractmethod
    def handle_silence(self: Self) -> str:
        """
        Used to handle occasions where users do not respond/reply for a period of time
        """
        ...
