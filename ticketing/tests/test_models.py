import datetime
import uuid
from django.test import TestCase
from django.utils import timezone
from django.db.utils import IntegrityError
from ticketing.models import Event, Attendee, Ticket


class ModelTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            title="Async Python Summit",
            description="All about asyncio and concurrency in Python.",
            location="Seattle, WA",
            event_date=timezone.now() + datetime.timedelta(days=10),
            total_capacity=10,
            tickets_sold=0,
        )

    def test_event_auto_slug_creation(self):
        self.assertEqual(self.event.slug, "async-python-summit")

    def test_event_slug_collision_resolution(self):
        duplicate_event = Event.objects.create(
            title="Async Python Summit",
            description="Duplicate event test",
            location="Seattle, WA",
            event_date=timezone.now() + datetime.timedelta(days=10),
            total_capacity=5,
        )
        self.assertTrue(duplicate_event.slug.startswith("async-python-summit-"))
        self.assertNotEqual(self.event.slug, duplicate_event.slug)

    def test_event_computed_properties(self):
        self.assertFalse(self.event.is_sold_out)
        self.assertEqual(self.event.tickets_remaining, 10)
        self.assertEqual(self.event.occupancy_percentage, 0.0)

        # Update tickets sold
        self.event.tickets_sold = 5
        self.event.save()
        self.assertFalse(self.event.is_sold_out)
        self.assertEqual(self.event.tickets_remaining, 5)
        self.assertEqual(self.event.occupancy_percentage, 50.0)

        # Reach capacity
        self.event.tickets_sold = 10
        self.event.save()
        self.assertTrue(self.event.is_sold_out)
        self.assertEqual(self.event.tickets_remaining, 0)
        self.assertEqual(self.event.occupancy_percentage, 100.0)

    def test_attendee_creation(self):
        attendee = Attendee.objects.create(name="Jane Doe", email="jane@example.com")
        self.assertEqual(str(attendee), "Jane Doe <jane@example.com>")

        # Email uniqueness constraint
        with self.assertRaises(IntegrityError):
            Attendee.objects.create(name="Another Jane", email="jane@example.com")

    def test_ticket_uuid_generation(self):
        attendee = Attendee.objects.create(name="John Smith", email="john@example.com")
        ticket = Ticket.objects.create(event=self.event, attendee=attendee)

        self.assertTrue(ticket.ticket_code)
        # Verify valid UUID format
        parsed_uuid = uuid.UUID(ticket.ticket_code)
        self.assertEqual(str(parsed_uuid), ticket.ticket_code)
