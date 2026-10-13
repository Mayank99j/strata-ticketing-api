# Strata Event Ticketing Backend

> **A high-reliability, concurrency-safe event ticketing platform and REST API engineered with Django 6, Django REST Framework (DRF), and SQLite.**

---

## 1. Executive Summary & Engineering Highlights

The primary engineering challenge in ticketing engines is **preventing race conditions and overselling** when hundreds of concurrent users attempt to purchase the final seats of a high-demand event in the exact same millisecond.

Strata guarantees **zero overselling** by combining:
1. **Pessimistic Row-Level Locking:** Acquiring an exclusive lock on the `Event` row using `select_for_update()`.
2. **ACID Transaction Isolation:** Executing the entire booking sequence inside an atomic transaction block (`transaction.atomic()`).
3. **Database-Level Invariant Enforcement:** SQLite `CheckConstraint(tickets_sold <= total_capacity)`.
4. **Immediate Transaction Serialization:** Configured SQLite `transaction_mode: 'IMMEDIATE'` and Write-Ahead Logging (WAL) to ensure concurrent transactions queue smoothly without deadlock.

---

## 2. Design System & Color Palette

Strata follows a strict utilitarian design system crafted for dense, functional operational dashboards:
- **Primary Background:** Off-White (`#F8FAFC` / `#F4F6F8`)
- **Secondary Surface / Cards:** Pure White (`#FFFFFF`) with thin borders (`#E2E8F0`)
- **Accent 1 (Primary Action & Confirmations):** Royal Blue (`#1D4ED8` / `#2563EB`)
- **Accent 2 (Headers, Critical Text, Primary Badges):** Deep Slate (`#0F172A`)
- **Body Text:** Charcoal Slate (`#334155`)
- **Muted Text / Meta:** Cool Grey (`#64748B`)
- **Border & Separator:** Cool Grey Light (`#E2E8F0`)
- **Typography:** System Sans (`Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`) with structured tabular numerals (`font-variant-numeric: tabular-nums`) for ticket counts and latency metrics.

---

## 3. Database Schema (`ticketing/models.py`)

### `Event`
- `title`: `CharField(max_length=200)`
- `slug`: `SlugField(unique=True, blank=True)` (auto-generated from title with collision handling)
- `description`: `TextField()`
- `location`: `CharField(max_length=200)`
- `event_date`: `DateTimeField()`
- `total_capacity`: `PositiveIntegerField()`
- `tickets_sold`: `PositiveIntegerField(default=0)`
- `created_at`: `DateTimeField(auto_now_add=True)`
- **Properties & Invariants:**
  - `is_sold_out`: Checks `tickets_sold >= total_capacity`
  - `tickets_remaining`: Returns `max(0, total_capacity - tickets_sold)`
  - `occupancy_percentage`: Returns `round((tickets_sold / total_capacity) * 100, 1)`
  - `CheckConstraint(condition=tickets_sold <= total_capacity)`

### `Attendee`
- `name`: `CharField(max_length=150)`
- `email`: `EmailField(unique=True)`
- `created_at`: `DateTimeField(auto_now_add=True)`

### `Ticket`
- `ticket_code`: `CharField(max_length=36, unique=True)` (auto-generated UUIDv4 string on creation)
- `event`: `ForeignKey(Event, on_delete=CASCADE, related_name='tickets')`
- `attendee`: `ForeignKey(Attendee, on_delete=CASCADE, related_name='tickets')`
- `booked_at`: `DateTimeField(auto_now_add=True)`

---

## 4. Concurrency Safety Implementation

In `ticketing/services.py`:

```python
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound
from .models import Event, Attendee, Ticket

def book_ticket(event_id: int, name: str, email: str) -> Ticket:
    with transaction.atomic():
        # Row-level lock: blocks all concurrent transactions until this commit finishes
        event = Event.objects.select_for_update().get(id=event_id)
        
        # Guard against overselling
        if event.tickets_sold >= event.total_capacity:
            raise ValidationError({"error": "Event is completely sold out."})
        
        # Get or create attendee record
        attendee, _ = Attendee.objects.get_or_create(
            email=email.strip().lower(),
            defaults={"name": name.strip()}
        )
        
        # Create ticket and atomically increment counter
        ticket = Ticket.objects.create(event=event, attendee=attendee)
        event.tickets_sold += 1
        event.save(update_fields=['tickets_sold'])

    return ticket
```

### Why this prevents race conditions:
1. When Thread A enters `select_for_update()`, SQLite acquires a write lock (`BEGIN IMMEDIATE`).
2. Thread B attempts to enter the same block, but its lock request waits in SQLite's busy queue.
3. Thread A increments `tickets_sold` from `49` to `50` and commits.
4. Thread B acquires the lock, re-reads the updated row, sees `tickets_sold == 50 >= total_capacity`, and raises `ValidationError("Event is completely sold out.")` (HTTP 400).
5. Overselling is physically impossible.

---

## 5. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/events/` | List all events (`?status=available`, `?status=sold_out`, `?search=...`) |
| `GET` | `/api/events/{id}/` | Retrieve single event detail & capacity metrics |
| `POST` | `/api/events/{id}/book/` | **Concurrency-safe ticket booking** (`{"name": "...", "email": "..."}`) |
| `GET` | `/api/events/{id}/tickets/` | List tickets booked for an event |
| `POST` | `/api/events/{id}/reset/` | Utility endpoint to reset capacity or sold count for testing |
| `GET` | `/api/tickets/` | List tickets (searchable by code, attendee email, event title) |
| `GET` | `/api/tickets/{ticket_code}/`| Retrieve ticket verification details by UUID code |
| `GET` | `/api/attendees/` | List registered attendees |
| `GET` | `/api/metrics/` | Platform metrics (occupancy rate, tickets sold, remaining) |
| `POST` | `/api/concurrency/simulate/`| Spawns multi-threaded simulated booking requests to test row locks |

---

## 6. User Interface & Concurrency Lab

The web interface is available directly at the server root:
1. **Events Catalog (`/`):**
   - Live platform metrics banner (Total Events, Platform Capacity, Tickets Issued, System Occupancy).
   - Real-time event search & filter pills (`All Events`, `Available`, `Sold Out`).
   - Event cards with tabular counters (`47 / 50 booked`, `3 remaining`), status badges, and capacity progress bar.
   - Interactive booking modal with asynchronous booking and instant printable receipt.
2. **Concurrency Lab (`/concurrency-lab/`):**
   - Interactive testing ground where developers can dispatch 10 to 30 concurrent threads competing for the last seats.
   - Real-time audit telemetry table logging per-thread latency, HTTP status code (201 vs 400), and verification verdict.
   - One-click "Reset Event Capacity" button to re-run simulations at will.
3. **Ticket Verification (`/verify/`):**
   - Authenticates UUID ticket codes against the registry.
4. **Django Admin (`/admin/`):**
   - Comprehensive dashboard with occupancy progress bars, colored status badges, capacity reset actions, and filter by availability.
   - Pre-seeded admin user: `admin` / `admin12345`.

---

## 7. CLI Commands & Quickstart

### Run the Development Server
```bash
python manage.py runserver
```
Visit:
- Web Application: http://127.0.0.1:8000/
- Concurrency Lab: http://127.0.0.1:8000/concurrency-lab/
- REST API: http://127.0.0.1:8000/api/
- Django Admin: http://127.0.0.1:8000/admin/ (Credentials: `admin` / `admin12345`)

### Seed Realistic Demo Data
```bash
python manage.py seed_data --clear
```

### Run Live Concurrency Stress Test via CLI
```bash
python manage.py test_concurrency --event-id 1 --requests 15
```

### Run Automated Test Suite
```bash
python manage.py test --noinput
```
Includes 16 automated tests covering models, API endpoints, error handling, and multi-threaded race condition safety.
