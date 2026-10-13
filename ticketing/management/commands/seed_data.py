import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from ticketing.models import Event, Attendee, Ticket

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds database with realistic events, attendees, tickets, and an admin superuser."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Wipes existing ticketing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing tickets, attendees, and events...")
            Ticket.objects.all().delete()
            Attendee.objects.all().delete()
            Event.objects.all().delete()

        # 1. Create or retrieve superuser
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@strata.io',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('admin12345')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created superuser 'admin' with password 'admin12345'"))
        else:
            self.stdout.write("Superuser 'admin' already exists.")

        # 2. Define events
        now = timezone.now()
        events_spec = [
            {
                "title": "Strata Distributed Systems & Concurrency Summit 2026",
                "slug": "strata-concurrency-summit-2026",
                "description": "Deep dive into ACID transaction isolation levels, row-level pessimistic locking, distributed consensus algorithms, and high-throughput backend architecture.",
                "location": "Moscone Center, San Francisco, CA",
                "event_date": now + datetime.timedelta(days=25, hours=9),
                "total_capacity": 50,
                "initial_sold": 47,  # Only 3 tickets left!
            },
            {
                "title": "Global AI Systems & LLM Infrastructure Conference",
                "slug": "global-ai-infrastructure-2026",
                "description": "Production engineering for generative AI systems, GPU cluster scheduling, low-latency inferencing pipelines, and enterprise safety guardrails.",
                "location": "ExCeL London, United Kingdom",
                "event_date": now + datetime.timedelta(days=45, hours=10),
                "total_capacity": 20,
                "initial_sold": 20,  # Completely sold out!
            },
            {
                "title": "High-Performance Python & Django Masterclass",
                "slug": "high-perf-python-django-2026",
                "description": "Hands-on masterclass optimizing Django ORM querysets, connection pooling, Redis caching patterns, and async ASGI throughput.",
                "location": "Berlin Congress Center, Germany",
                "event_date": now + datetime.timedelta(days=32, hours=13),
                "total_capacity": 30,
                "initial_sold": 12,  # 18 remaining
            },
            {
                "title": "Database Internals & Transaction Safety Lab",
                "slug": "database-internals-safety-lab",
                "description": "Intimate hands-on laboratory exploring lock contention, write-ahead logging (WAL), deadlock resolution, and atomic row-level isolation.",
                "location": "Seattle Convention Center, WA",
                "event_date": now + datetime.timedelta(days=15, hours=14),
                "total_capacity": 5,
                "initial_sold": 0,  # 5 remaining (Prime target for concurrency testing)
            },
            {
                "title": "Enterprise Cloud Security & Zero-Trust Architecture",
                "slug": "enterprise-cloud-security-2027",
                "description": "Comprehensive strategies for identity boundaries, workload segmentation, cryptographic verification, and audit compliance.",
                "location": "Marina Bay Sands, Singapore",
                "event_date": now + datetime.timedelta(days=90, hours=9),
                "total_capacity": 60,
                "initial_sold": 8,  # 52 remaining
            },
        ]

        # Seed attendee pools
        names_pool = [
            ("Alex Mercer", "alex.mercer@apex.dev"),
            ("Elena Rostova", "elena.rostova@cyber.tech"),
            ("Marcus Vance", "marcus.v@cloudscale.io"),
            ("Priya Sharma", "priya.sharma@datadrive.net"),
            ("David Kim", "d.kim@nextgen.co"),
            ("Sarah Jenkins", "s.jenkins@infraspec.org"),
            ("Tariq Al-Mansoor", "tariq@vertex.ai"),
            ("Chloe Dubois", "c.dubois@algoworks.eu"),
            ("Hiroshi Tanaka", "h.tanaka@tokyolabs.jp"),
            ("Amara Okafor", "a.okafor@lagostech.io"),
            ("Carlos Santana", "c.santana@devcore.sa"),
            ("Ingrid Bergman", "ingrid@nordicdata.se"),
        ]

        for spec in events_spec:
            event, created = Event.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "description": spec["description"],
                    "location": spec["location"],
                    "event_date": spec["event_date"],
                    "total_capacity": spec["total_capacity"],
                    "tickets_sold": 0,
                }
            )

            # Update details if existing
            event.title = spec["title"]
            event.description = spec["description"]
            event.location = spec["location"]
            event.event_date = spec["event_date"]
            event.total_capacity = spec["total_capacity"]

            # Issue tickets up to initial_sold
            current_tickets_count = event.tickets.count()
            needed_tickets = spec["initial_sold"] - current_tickets_count

            if needed_tickets > 0:
                for i in range(needed_tickets):
                    idx = (current_tickets_count + i) % len(names_pool)
                    base_name, base_domain = names_pool[idx]
                    user_num = current_tickets_count + i + 1
                    email = f"user{user_num}.{base_domain}"
                    name = f"{base_name} ({user_num})"

                    attendee, _ = Attendee.objects.get_or_create(
                        email=email,
                        defaults={"name": name}
                    )
                    Ticket.objects.create(event=event, attendee=attendee)

            event.tickets_sold = event.tickets.count()
            event.save()
            self.stdout.write(
                f"Seeded Event: '{event.title}' -> {event.tickets_sold}/{event.total_capacity} sold "
                f"({event.tickets_remaining} left, sold_out={event.is_sold_out})"
            )

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
