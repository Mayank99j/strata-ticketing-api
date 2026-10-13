import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import transaction, models
from rest_framework.exceptions import ValidationError, NotFound

from .models import Event, Attendee, Ticket

logger = logging.getLogger(__name__)


def book_ticket(event_id: int, name: str, email: str) -> Ticket:
    """
    Executes a concurrency-safe ticket purchase for the specified event.
    
    Uses Django's atomic database transaction block combined with
    `select_for_update()` to enforce row-level locking on the Event row.
    This strictly guarantees that simultaneous concurrent transactions cannot
    read a stale `tickets_sold` counter or oversell past `total_capacity`.
    """
    if not name or not name.strip():
        raise ValidationError({"error": "Attendee name is required."})
    if not email or not email.strip():
        raise ValidationError({"error": "Attendee email is required."})

    cleaned_email = email.strip().lower()
    cleaned_name = name.strip()

    max_retries = 8
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                try:
                    # Row-level lock to prevent simultaneous race conditions
                    event = Event.objects.select_for_update().get(id=event_id)
                except Event.DoesNotExist:
                    raise NotFound({"error": f"Event with ID {event_id} does not exist."})

                if event.tickets_sold >= event.total_capacity:
                    raise ValidationError({"error": "Event is completely sold out."})

                # Get or create attendee
                attendee, created = Attendee.objects.get_or_create(
                    email=cleaned_email,
                    defaults={"name": cleaned_name}
                )
                if not created and cleaned_name and attendee.name != cleaned_name:
                    attendee.name = cleaned_name
                    attendee.save(update_fields=['name'])

                # Create ticket and increment counter
                ticket = Ticket.objects.create(event=event, attendee=attendee)
                event.tickets_sold += 1
                event.save(update_fields=['tickets_sold'])

            return ticket
        except Exception as exc:
            # Check if this is a transient SQLite database lock error
            from django.db import OperationalError
            if isinstance(exc, OperationalError) and "locked" in str(exc).lower():
                if attempt < max_retries - 1:
                    import random
                    sleep_time = 0.02 * (1.5 ** attempt) + random.uniform(0.005, 0.02)
                    time.sleep(sleep_time)
                    continue
            raise



def get_event_metrics() -> dict:
    """
    Calculates platform-wide capacity and booking metrics.
    """
    events = Event.objects.all()
    aggregates = events.aggregate(
        total_events=models.Count('id'),
        total_capacity=models.Sum('total_capacity'),
        total_sold=models.Sum('tickets_sold')
    )

    total_events = aggregates['total_events'] or 0
    total_capacity = aggregates['total_capacity'] or 0
    total_sold = aggregates['total_sold'] or 0
    total_remaining = max(0, total_capacity - total_sold)

    sold_out_count = sum(1 for e in events if e.is_sold_out)
    total_attendees = Attendee.objects.count()
    total_tickets = Ticket.objects.count()

    occupancy_rate = round((total_sold / total_capacity * 100), 1) if total_capacity > 0 else 0.0

    return {
        "total_events": total_events,
        "total_capacity": total_capacity,
        "total_tickets_sold": total_sold,
        "total_tickets_remaining": total_remaining,
        "sold_out_events": sold_out_count,
        "occupancy_rate": occupancy_rate,
        "total_attendees": total_attendees,
        "total_tickets_issued": total_tickets,
    }


def simulate_concurrent_bookings(event_id: int, num_requests: int = 10) -> dict:
    """
    Simulates simultaneous concurrent booking requests against a target event
    using a multi-threaded pool to stress test and prove concurrency safety.
    """
    try:
        target_event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise NotFound({"error": f"Event with ID {event_id} does not exist."})

    initial_sold = target_event.tickets_sold
    initial_remaining = target_event.tickets_remaining
    capacity = target_event.total_capacity

    results = []

    def _worker(thread_idx: int):
        thread_start = time.perf_counter()
        sim_email = f"user_{thread_idx}_{int(time.time() * 1000)}@stress-test.local"
        sim_name = f"Concurrent Tester #{thread_idx}"
        try:
            ticket = book_ticket(event_id=event_id, name=sim_name, email=sim_email)
            elapsed = round((time.perf_counter() - thread_start) * 1000, 2)
            return {
                "thread_index": thread_idx,
                "status": "SUCCESS",
                "http_status": 201,
                "ticket_code": ticket.ticket_code,
                "email": sim_email,
                "latency_ms": elapsed,
                "message": "Ticket successfully booked",
            }
        except ValidationError as ve:
            elapsed = round((time.perf_counter() - thread_start) * 1000, 2)
            err_msg = ve.detail.get("error", str(ve.detail)) if hasattr(ve, 'detail') and isinstance(ve.detail, dict) else str(ve)
            return {
                "thread_index": thread_idx,
                "status": "SOLD_OUT",
                "http_status": 400,
                "ticket_code": None,
                "email": sim_email,
                "latency_ms": elapsed,
                "message": err_msg,
            }
        except Exception as ex:
            elapsed = round((time.perf_counter() - thread_start) * 1000, 2)
            return {
                "thread_index": thread_idx,
                "status": "ERROR",
                "http_status": 500,
                "ticket_code": None,
                "email": sim_email,
                "latency_ms": elapsed,
                "message": str(ex),
            }
        finally:
            from django.db import connection
            connection.close()


    overall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(num_requests, 32)) as executor:
        futures = [executor.submit(_worker, i + 1) for i in range(num_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    overall_duration_ms = round((time.perf_counter() - overall_start) * 1000, 2)

    # Sort results by thread_index for predictable inspection
    results.sort(key=lambda x: x["thread_index"])

    target_event.refresh_from_db()
    final_sold = target_event.tickets_sold
    final_remaining = target_event.tickets_remaining

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    sold_out_count = sum(1 for r in results if r["status"] == "SOLD_OUT")
    error_count = sum(1 for r in results if r["status"] == "ERROR")

    # Verification: Did tickets sold ever exceed capacity?
    oversold = final_sold > capacity
    expected_success = min(initial_remaining, num_requests)
    race_condition_detected = oversold or (final_sold != initial_sold + success_count)

    return {
        "event_id": target_event.id,
        "event_title": target_event.title,
        "total_capacity": capacity,
        "initial_sold": initial_sold,
        "initial_remaining": initial_remaining,
        "num_concurrent_requests": num_requests,
        "successful_bookings": success_count,
        "sold_out_rejections": sold_out_count,
        "unexpected_errors": error_count,
        "final_sold": final_sold,
        "final_remaining": final_remaining,
        "oversold": oversold,
        "concurrency_safe": not race_condition_detected and not oversold,
        "overall_duration_ms": overall_duration_ms,
        "thread_results": results,
    }
