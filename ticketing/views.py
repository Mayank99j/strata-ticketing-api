from django.shortcuts import render, get_object_or_404
from django.db.models import Q, F
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError, NotFound

from .models import Event, Attendee, Ticket
from .serializers import (
    EventSerializer,
    TicketSerializer,
    AttendeeSerializer,
    BookingRequestSerializer,
    ConcurrencySimulationSerializer,
    CapacityResetSerializer,
)
from .services import book_ticket, get_event_metrics, simulate_concurrent_bookings


# ============================================================================
# REST API ViewSets & Views
# ============================================================================

class EventViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Events with concurrency-safe booking and metrics actions.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['event_date', 'total_capacity', 'tickets_sold', 'created_at']
    ordering = ['event_date']

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter == 'sold_out':
            qs = qs.filter(tickets_sold__gte=F('total_capacity'))
        elif status_filter == 'available':
            qs = qs.filter(tickets_sold__lt=F('total_capacity'))
        return qs

    @action(detail=True, methods=['post'], url_path='book')
    def book(self, request, pk=None):
        """
        Concurrency-safe ticket booking endpoint for this event.
        Guarantees zero overselling via row-level lock and atomic transaction.
        """
        event = self.get_object()
        serializer = BookingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        email = serializer.validated_data['email']

        ticket = book_ticket(event_id=event.id, name=name, email=email)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='tickets')
    def event_tickets(self, request, pk=None):
        """
        Retrieves all issued tickets for this event.
        """
        event = self.get_object()
        tickets = event.tickets.select_related('attendee').all()
        return Response(TicketSerializer(tickets, many=True).data)

    @action(detail=True, methods=['post'], url_path='reset')
    def reset_capacity(self, request, pk=None):
        """
        Utility action to reset event sold counter or adjust capacity for testing.
        """
        event = self.get_object()
        reset_sold = request.data.get('reset_sold', True)
        new_capacity = request.data.get('total_capacity')

        if new_capacity is not None:
            try:
                new_cap = int(new_capacity)
                if new_cap < 1:
                    return Response({"error": "Capacity must be >= 1"}, status=status.HTTP_400_BAD_REQUEST)
                event.total_capacity = new_cap
            except ValueError:
                return Response({"error": "Invalid capacity value"}, status=status.HTTP_400_BAD_REQUEST)

        if reset_sold:
            event.tickets.all().delete()
            event.tickets_sold = 0

        event.save()
        return Response(EventSerializer(event).data)


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for querying tickets and ticket codes.
    """
    queryset = Ticket.objects.select_related('event', 'attendee').all()
    serializer_class = TicketSerializer
    lookup_field = 'ticket_code'
    filter_backends = [filters.SearchFilter]
    search_fields = ['ticket_code', 'attendee__name', 'attendee__email', 'event__title']

    @action(detail=False, methods=['post'], url_path='book')
    def direct_book(self, request):
        """
        Direct booking endpoint accepting {event_id, name, email}.
        """
        event_id = request.data.get('event_id')
        name = request.data.get('name')
        email = request.data.get('email')

        if not event_id:
            raise ValidationError({"event_id": "Event ID is required."})

        ticket = book_ticket(event_id=event_id, name=name, email=email)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class AttendeeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for Attendee records.
    """
    queryset = Attendee.objects.prefetch_related('tickets').all()
    serializer_class = AttendeeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'email']


class MetricsAPIView(APIView):
    """
    Returns platform-wide metrics and booking statistics.
    """
    def get(self, request):
        metrics = get_event_metrics()
        return Response(metrics)


class ConcurrencySimulationAPIView(APIView):
    """
    Executes a multi-threaded concurrent stress test against an event to prove
    that select_for_update() and transaction.atomic() strictly prevent overselling.
    """
    def post(self, request):
        serializer = ConcurrencySimulationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_id = serializer.validated_data['event_id']
        num_requests = serializer.validated_data.get('num_requests', 10)

        simulation_result = simulate_concurrent_bookings(
            event_id=event_id,
            num_requests=num_requests
        )
        return Response(simulation_result, status=status.HTTP_200_OK)


# ============================================================================
# Clean, Utilitarian Web UI Views
# ============================================================================

def ui_event_list(request):
    """
    Render main event catalog, metrics banner, and booking interface.
    """
    metrics = get_event_metrics()
    events = Event.objects.all().order_by('event_date')
    return render(request, 'ticketing/index.html', {
        'metrics': metrics,
        'events': events,
    })


def ui_event_detail(request, pk):
    """
    Render single event detail view with tickets issued.
    """
    event = get_object_or_404(Event, pk=pk)
    tickets = event.tickets.select_related('attendee').order_by('-booked_at')[:20]
    return render(request, 'ticketing/event_detail.html', {
        'event': event,
        'tickets': tickets,
    })


def ui_concurrency_lab(request):
    """
    Interactive test lab UI to simulate simultaneous booking race conditions.
    """
    events = Event.objects.all().order_by('title')
    return render(request, 'ticketing/concurrency_lab.html', {
        'events': events,
    })


def ui_ticket_verification(request, ticket_code=None):
    """
    Ticket lookup and verification page.
    """
    ticket = None
    searched_code = ticket_code or request.GET.get('code', '').strip()
    if searched_code:
        ticket = Ticket.objects.filter(ticket_code=searched_code).select_related('event', 'attendee').first()
    return render(request, 'ticketing/ticket_verify.html', {
        'ticket': ticket,
        'searched_code': searched_code,
    })
