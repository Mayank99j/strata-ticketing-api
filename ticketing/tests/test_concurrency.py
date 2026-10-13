import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from ticketing.models import Event, Attendee, Ticket
from ticketing.services import book_ticket, simulate_concurrent_bookings


class ConcurrencySafetyTests(TransactionTestCase):
    """
    Validates concurrency safety, row-level locking, and zero-overselling
    guarantees under simultaneous multi-threaded ticket booking load.
    """

    def setUp(self):
        self.event = Event.objects.create(
            title="High-Contention Concurrency Test Event",
            description="Testing simultaneous transactions on the last remaining seats.",
            location="Virtual / ThreadPool",
            event_date=timezone.now() + datetime.timedelta(days=5),
            total_capacity=5,
            tickets_sold=0,
        )

    def tearDown(self):
        from django.db import connections
        connections.close_all()
        super().tearDown()

    def test_concurrent_bookings_prevent_overselling(self):
        """
        Spawns 20 simultaneous threads competing for only 5 total seats.
        Strictly asserts:
        1. Exactly 5 bookings succeed (HTTP 201 equivalent).
        2. Exactly 15 requests are rejected with sold out ValidationError (HTTP 400).
        3. Database tickets_sold is exactly 5 (never > 5).
        4. Total Ticket records created in database is exactly 5.
        """
        num_threads = 20
        capacity = self.event.total_capacity
        successful_tickets = []
        sold_out_exceptions = []
        other_exceptions = []

        def _purchase_task(thread_id: int):
            try:
                ticket = book_ticket(
                    event_id=self.event.id,
                    name=f"Worker {thread_id}",
                    email=f"worker_{thread_id}@concurrency-test.local"
                )
                return ("SUCCESS", ticket)
            except ValidationError as ve:
                return ("SOLD_OUT", str(ve))
            except Exception as ex:
                return ("OTHER_ERROR", str(ex))
            finally:
                from django.db import connection
                connection.close()


        # Launch concurrent threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(_purchase_task, i + 1) for i in range(num_threads)]
            for future in as_completed(futures):
                status_type, result = future.result()
                if status_type == "SUCCESS":
                    successful_tickets.append(result)
                elif status_type == "SOLD_OUT":
                    sold_out_exceptions.append(result)
                else:
                    other_exceptions.append(result)

        # Reload event from database to verify final state
        self.event.refresh_from_db()

        # Strict Assertions
        self.assertEqual(len(other_exceptions), 0, f"Unexpected errors: {other_exceptions}")
        self.assertEqual(len(successful_tickets), capacity, f"Expected exactly {capacity} successes, got {len(successful_tickets)}")
        self.assertEqual(len(sold_out_exceptions), num_threads - capacity, f"Expected {num_threads - capacity} rejections, got {len(sold_out_exceptions)}")
        
        # Verify database inventory invariant: tickets_sold == total_capacity
        self.assertEqual(self.event.tickets_sold, capacity)
        self.assertEqual(self.event.tickets_remaining, 0)
        self.assertTrue(self.event.is_sold_out)

        # Verify actual database ticket count matches inventory exactly
        actual_ticket_count = Ticket.objects.filter(event=self.event).count()
        self.assertEqual(actual_ticket_count, capacity)

    def test_concurrent_simulation_service(self):
        """
        Validates the simulate_concurrent_bookings service helper with 15 threads on 3 remaining seats.
        """
        # Set event to have only 3 seats remaining
        self.event.total_capacity = 10
        self.event.tickets_sold = 7
        self.event.save()

        result = simulate_concurrent_bookings(event_id=self.event.id, num_requests=15)

        self.assertTrue(result["concurrency_safe"])
        self.assertFalse(result["oversold"])
        self.assertEqual(result["successful_bookings"], 3)
        self.assertEqual(result["sold_out_rejections"], 12)
        self.assertEqual(result["final_sold"], 10)
        self.assertEqual(result["final_remaining"], 0)
