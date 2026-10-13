from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EventViewSet,
    TicketViewSet,
    AttendeeViewSet,
    MetricsAPIView,
    ConcurrencySimulationAPIView,
    ui_event_list,
    ui_event_detail,
    ui_concurrency_lab,
    ui_ticket_verification,
)

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'attendees', AttendeeViewSet, basename='attendee')

urlpatterns = [
    # UI Web Routes
    path('', ui_event_list, name='ui-event-list'),
    path('events/<int:pk>/', ui_event_detail, name='ui-event-detail'),
    path('concurrency-lab/', ui_concurrency_lab, name='ui-concurrency-lab'),
    path('verify/', ui_ticket_verification, name='ui-ticket-verify-search'),
    path('verify/<str:ticket_code>/', ui_ticket_verification, name='ui-ticket-verify'),

    # REST API Routes
    path('api/metrics/', MetricsAPIView.as_view(), name='api-metrics'),
    path('api/concurrency/simulate/', ConcurrencySimulationAPIView.as_view(), name='api-concurrency-simulate'),
    path('api/', include(router.urls)),
]
