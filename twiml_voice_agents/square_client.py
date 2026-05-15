from datetime import datetime, timezone
import os

from square import Square
from square.types.customer import Customer
from square.types.booking import Booking
from square.environment import SquareEnvironment
from square.core.api_error import ApiError
from square.requests.booking import BookingParams, AppointmentSegmentParams

from square.types.location_booking_profile import LocationBookingProfile
from square.types.team_member_booking_profile import TeamMemberBookingProfile
from square.types.search_catalog_items_response import SearchCatalogItemsResponse

from typing import List, Self

SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")

class SquareClient(Square):
    customer: Customer

    team_member_profiles: List[TeamMemberBookingProfile]
    team_member_ids: List[str]

    location_profiles: List[LocationBookingProfile]
    location_ids: List[str]

    def __init__(self: Self, customer_phone_number: str, access_token: str | None = None, *args, **kwargs):
        super().__init__(
            environment=SquareEnvironment.PRODUCTION,
            token=access_token or SQUARE_ACCESS_TOKEN,
            *args,
            **kwargs
        )
        self.get_locations()
        self.get_team_member_ids()
        self.get_or_create_customer_by_phone_num(customer_phone_number)

    def get_locations(self: Self):
        self.location_profiles = [ location for location in self.bookings.location_profiles.list() ] # iterates over SyncPager
        self.location_ids = [ location.location_id for location in self.location_profiles ]
        # print("self.location_ids:", self.location_ids)
        return self.location_ids

    def get_team_member_ids(self, location_id: str | None = None):
        self.team_member_profiles = [ tm for tm in self.bookings.team_member_profiles.list(location_id=location_id) ] # iterates over SyncPager
        self.team_member_ids = [ tm.team_member_id for tm in self.team_member_profiles ]
        # print("self.team_member_ids:", self.team_member_ids)
        return self.team_member_ids

    def get_service_variations(self):
        """
        Get APPOINTMENTS_SERVICE offerings from the catalog
        """
        response: SearchCatalogItemsResponse = self.catalog.search_items(enabled_location_ids=self.location_ids, product_types=["APPOINTMENTS_SERVICE"])
        self.catalog_items = [ item.item_data for item in response.items ]
        # print("self.catalog_items:", self.catalog_items)

        return self.catalog_items

    def get_or_create_customer_by_phone_num(self, phone_num: str) -> Customer:
        self.customer = self.search_customer_by_phone_num(phone_num)
        self.customer = self.customer if self.customer else self.create_customer_by_phone_num(phone_num)
        return self.customer

    def search_customer_by_phone_num(
        self,
        phone_num: str
    ) -> Customer | None:
        try:
            search_customers_resp = self.customers.search(
                count=True,
                query={
                    "filter": {
                        "phone_number": {
                            "exact": phone_num
                        }
                    }
                }
            )
            # print("search_customers_resp:", search_customers_resp)
        except ApiError as e:
            raise
        return search_customers_resp.customers[0] if search_customers_resp.customers else None

    def create_customer_by_phone_num(
        self,
        phone_num: str
    ):
        try:
            create_customer_resp = self.customers.create(
                phone_number=phone_num
            )
            print("create_customer_resp:", create_customer_resp)
        except ApiError as e:
            raise
        return create_customer_resp.customer

    @staticmethod
    def get_current_time() -> str:
        """
        Get the current time in a more human-readable format.
        """

        now = datetime.now(timezone.utc) # Get current time in local timezone
        current_time = now.strftime("%I:%M:%S %p %Z")  # Using 12-hour format with AM/PM
        current_date = now.strftime(
            "%A, %B %d, %Y"
        )  # Full weekday, month name, day, and year

        return f"Current Date and Time = {current_date}, {current_time}"

    def create_booking(
        self: Self,
        start_at: str, # an RFC 3339 datetime indicating when the appointment should start e.g. "2026-05-06T10:00:00-05:00"
        service_variation_id: str,
        service_variation_version: int
    ) -> str: # "Success" or "That time slot is no longer available."
        """
        Raises:
            ApiError: if the API returns an unexpected error.
        """
        location_id =self.location_ids[0] # HACK: ideally, this would flexibly handle multiple locations, but this should be fine for solopreneur clients
        team_member_id = self.team_member_ids[0] # HACK: ideally, we would want to account for team member availability and possibly customer preferences

        try:
            create_booking_resp = self.bookings.create(
                booking=BookingParams(
                    customer_id=self.customer.id,
                    start_at=start_at,
                    location_id=location_id,
                    appointment_segments=[
                        AppointmentSegmentParams(
                            team_member_id=team_member_id,
                            service_variation_id=service_variation_id,
                            service_variation_version=service_variation_version,
                        )
                    ],
                )
            )
        except ApiError as e:
            time_slot_not_avail_errs = [
                err
                for err in e.errors
                if err.category == "INVALID_REQUEST_ERROR"
                and err.field == "start_at"
                and err.detail == "That time slot is no longer available."
            ]
            if len(time_slot_not_avail_errs) > 0:
                return "That time slot is no longer available."
            else:
                raise

        return "Success"

    def get_customer_bookings(self: Self) -> List[Booking]:
        """
        Get a list of the customer's bookings, useful for features like allowing users to cancel or reschedule existing appointments.
        """
        try:
            list_bookings_resp = list(self.bookings.list(
                customer_id=self.customer.id
            ))
            print("list_bookings_resp:", list_bookings_resp)
        except ApiError as e:
            raise
        return list_bookings_resp

    def cancel_booking(
        self: Self,
        booking_id: str # an identifier for a `Booking`, get using `get_customer_bookings`
    ) -> str: # "Success" if the cancellation was successful
        """
        Cancel a booking by its ID.

        Raises:
            ApiError: if the API returns an unexpected error.
        """
        try:
            cancel_booking_resp = self.bookings.cancel(
                booking_id=booking_id
            )
            print("cancel_booking_resp:", cancel_booking_resp)
        except ApiError as e:
            raise
        return "Success"
