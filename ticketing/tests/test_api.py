import datetime
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from ticketing.models import Event, Attendee, Ticket


class APITests(APITestCase):
    def setUp(self):
        self.now = timezone.now()
        self.available_event = Event.objects.create(
            title="DevOps Live Summit",
            description="Continuous Delivery, Kubernetes, and Observability.",
            location="Chicago, IL",
            event_date=self.now + datetime.timedelta(days=14),
            total_capacity=5,
            tickets_sold=3,
        )
        self.sold_out_event = Event.objects.create(
            title="Exclusive Leadership Roundtable",
            description="Invitation only executive summit.",
            location="New York, NY",
            event_date=self.now + datetime.timedelta(days=7),
            total_capacity=2,
            tickets_sold=2,
        )
        self.attendee = Attendee.objects.create(
            name="Alice Cooper",
            email="alice@cooper.org"
        )
        self.ticket = Ticket.objects.create(
            event=self.available_event,
            attendee=self.attendee
        )

    def test_list_events(self):
        response = self.client.get('/api/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check paginated response
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)

    def test_filter_events_by_status(self):
        resp_avail = self.client.get('/api/events/?status=available')
        self.assertEqual(resp_avail.status_code, status.HTTP_200_OK)
        results_avail = resp_avail.data.get('results', resp_avail.data)
        self.assertEqual(len(results_avail), 1)
        self.assertEqual(results_avail[0]['id'], self.available_event.id)

        resp_sold = self.client.get('/api/events/?status=sold_out')
        self.assertEqual(resp_sold.status_code, status.HTTP_200_OK)
        results_sold = resp_sold.data.get('results', resp_sold.data)
        self.assertEqual(len(results_sold), 1)
        self.assertEqual(results_sold[0]['id'], self.sold_out_event.id)

    def test_get_event_detail(self):
        response = self.client.get(f'/api/events/{self.available_event.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], "DevOps Live Summit")
        self.assertEqual(response.data['tickets_remaining'], 2)
        self.assertFalse(response.data['is_sold_out'])

    def test_book_ticket_success(self):
        payload = {
            "name": "Bob Dylan",
            "email": "bob@dylan.org"
        }
        response = self.client.post(f'/api/events/{self.available_event.id}/book/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('ticket_code', response.data)
        self.assertEqual(response.data['attendee']['name'], "Bob Dylan")
        self.assertEqual(response.data['attendee']['email'], "bob@dylan.org")

        self.available_event.refresh_from_db()
        self.assertEqual(self.available_event.tickets_sold, 4)
        self.assertEqual(self.available_event.tickets_remaining, 1)

    def test_book_ticket_sold_out_error(self):
        payload = {
            "name": "Charlie Brown",
            "email": "charlie@peanuts.com"
        }
        response = self.client.post(f'/api/events/{self.sold_out_event.id}/book/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completely sold out", str(response.data))

    def test_book_ticket_invalid_data(self):
        response = self.client.post(f'/api/events/{self.available_event.id}/book/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_platform_metrics_endpoint(self):
        response = self.client.get('/api/metrics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_events'], 2)
        self.assertEqual(response.data['total_capacity'], 7)
        self.assertEqual(response.data['total_tickets_sold'], 5)
        self.assertEqual(response.data['sold_out_events'], 1)

    def test_ticket_lookup_endpoint(self):
        response = self.client.get(f'/api/tickets/{self.ticket.ticket_code}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ticket_code'], self.ticket.ticket_code)
        self.assertEqual(response.data['attendee']['email'], "alice@cooper.org")

    def test_ui_routes_render(self):
        # Index
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Strata Event Ticketing")

        # Detail
        resp_detail = self.client.get(f'/events/{self.available_event.id}/')
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "DevOps Live Summit")

        # Concurrency Lab
        resp_lab = self.client.get('/concurrency-lab/')
        self.assertEqual(resp_lab.status_code, 200)
        self.assertContains(resp_lab, "Concurrency & Race Condition Lab")

        # Verification
        resp_verify = self.client.get(f'/verify/?code={self.ticket.ticket_code}')
        self.assertEqual(resp_verify.status_code, 200)
        self.assertContains(resp_verify, "VALID TICKET CONFIRMED")
