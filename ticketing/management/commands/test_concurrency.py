from django.core.management.base import BaseCommand
from ticketing.models import Event
from ticketing.services import simulate_concurrent_bookings


class Command(BaseCommand):
    help = "Simulates concurrent race conditions against an event to verify zero overselling."

    def add_arguments(self, parser):
        parser.add_argument(
            '--event-id',
            type=int,
            default=None,
            help='ID of target event to stress test. If not specified, picks first available event with remaining seats.',
        )
        parser.add_argument(
            '--requests',
            type=int,
            default=15,
            help='Number of simultaneous concurrent threads to spawn (default: 15).',
        )

    def handle(self, *args, **options):
        event_id = options.get('event_id')
        num_requests = options.get('requests', 15)

        if event_id:
            try:
                event = Event.objects.get(id=event_id)
            except Event.DoesNotExist:
                self.stderr.write(f"Event with ID {event_id} does not exist.")
                return
        else:
            event = Event.objects.filter(tickets_sold__lt=Event.objects.filter(pk=Event.objects.values('pk')[:1]).values('total_capacity')[:1]).first()
            if not event:
                event = Event.objects.exclude(tickets_sold__gte=1000).first()

        if not event:
            self.stderr.write("No events found in database. Run `python manage.py seed_data` first.")
            return

        self.stdout.write(self.style.NOTICE(f"\n========================================================"))
        self.stdout.write(self.style.NOTICE(f"   STRATA CONCURRENCY STRESS TEST (ROW-LEVEL LOCK)"))
        self.stdout.write(self.style.NOTICE(f"========================================================"))
        self.stdout.write(f"Target Event: '{event.title}' (ID: {event.id})")
        self.stdout.write(f"Venue: {event.location}")
        self.stdout.write(f"Total Capacity: {event.total_capacity}")
        self.stdout.write(f"Initial Sold: {event.tickets_sold} | Initial Remaining: {event.tickets_remaining}")
        self.stdout.write(f"Spawning {num_requests} concurrent threads firing simultaneously...\n")

        result = simulate_concurrent_bookings(event_id=event.id, num_requests=num_requests)

        self.stdout.write(f"Test Execution Duration: {result['overall_duration_ms']} ms")
        self.stdout.write(f"Successful Bookings (201 Created): {result['successful_bookings']}")
        self.stdout.write(f"Sold-Out Rejections (400 Bad Request): {result['sold_out_rejections']}")
        self.stdout.write(f"Unexpected Errors: {result['unexpected_errors']}")
        self.stdout.write(f"Final Tickets Sold: {result['final_sold']} / {result['total_capacity']}")
        self.stdout.write(f"Final Remaining: {result['final_remaining']}")

        self.stdout.write("\nIndividual Thread Breakdown:")
        self.stdout.write(f"{'Thread':<8} {'Status':<12} {'HTTP':<6} {'Latency':<10} {'Ticket Code'}")
        self.stdout.write("-" * 65)
        for tr in result['thread_results']:
            code = tr['ticket_code'][:8] + '...' if tr['ticket_code'] else '---'
            status_color = self.style.SUCCESS if tr['status'] == 'SUCCESS' else self.style.WARNING
            self.stdout.write(
                f"#{tr['thread_index']:<7} "
                f"{status_color(tr['status']):<21} "
                f"{tr['http_status']:<6} "
                f"{tr['latency_ms']:<6} ms  "
                f"{code}"
            )

        self.stdout.write("\n" + "=" * 65)
        if result['concurrency_safe'] and not result['oversold']:
            self.stdout.write(
                self.style.SUCCESS(
                    "VERIFICATION PASSED: Zero Overselling Detected!\n"
                    "Row-level locks via select_for_update() and transaction.atomic() strictly prevented race conditions."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR("VERIFICATION FAILED: Overselling or race condition detected.")
            )
        self.stdout.write("=" * 65 + "\n")
