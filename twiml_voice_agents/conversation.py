from .agent import VirtualAgent
from claudette import *
from .square_client import SquareClient
from typing import Self

class Conversation(VirtualAgent, Chat):
    square_client: SquareClient

    def __init__(self: Self, from_num: str, forwarded_from_num: str | None, to_num: str, call_sid: str, system_prompt: str = ''):
        self.square_client = SquareClient(from_num)

        super().__init__(
            sp=system_prompt,
            model="claude-haiku-4-5",
            tools=[
                self.square_client.get_service_variations, SquareClient.get_current_time, self.create_booking, # related to creating bookings
                self.square_client.get_customer_bookings, self.cancel_booking # related to cancelling bookings
            ]
        )
        self.from_num = from_num
        self.forwarded_from_num = forwarded_from_num
        self.to_num = to_num
        self.call_sid = call_sid

    @property
    def opening_line(self: Self):
        """
        Greeting and/or prompt for caller
        Not included in chat history
        Only intended to help caller start conversation with agent

        This exists because both Anthropic and OpenAI APIs expect "user" messages to precede any "assistant" (agent) messages
        """
        return (
            "Hello! I can help you schedule appointments, list appointments, and cancel appointments."
        )

    def get_next_response(self, user_input: str) -> str:
        """
        Runs tool loop and returns LLM's latest text response
        """
        llm_responses = self.toolloop(user_input)
        for llm_response in llm_responses:
            print(f"llm_response ({type(llm_response)}): {llm_response}")
        # print(list(llm_responses)) # exhaust the generator to run all tools and get to the final response

        response_for_user = llm_responses.value[-1]["content"][0]["text"]
        return response_for_user

    # adds documentation specific for tool calling
    def create_booking(
        self: Self,
        start_at: str, # an RFC 3339 datetime indicating when the appointment should start e.g. "2026-05-06T10:00:00-05:00"
        service_variation_id: str, # identifies service item along with version, get using `get_service_variations` tool
        service_variation_version: int # identifies service item along with id, get using `get_service_variations` tool
    ) -> str:
        """

        returns "Success" or "That time slot is no longer available."

        Raises:
            ApiError: if the API returns an unexpected error.
        """
        self.square_client.create_booking(
            start_at,
            service_variation_id,
            service_variation_version
        )

    # adds documentation specific for tool calling
    def cancel_booking(
        self: Self,
        booking_id: str # an identifier for a `Booking`, get using `get_customer_bookings` tool
    ) -> str: # "Success" if the cancellation was successful.
        """
        Cancel a booking by its ID.

        Raises:
            ApiError: if the API returns an unexpected error.
        """
        self.square_client.cancel_booking(
            booking_id
        )
