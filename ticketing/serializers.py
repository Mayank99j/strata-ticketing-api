from rest_framework import serializers
from .models import Event, Attendee, Ticket


class AttendeeSerializer(serializers.ModelSerializer):
    tickets_count = serializers.IntegerField(source='tickets.count', read_only=True)

    class Meta:
        model = Attendee
        fields = ['id', 'name', 'email', 'created_at', 'tickets_count']
        read_only_fields = ['id', 'created_at', 'tickets_count']


class EventSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['id', 'title', 'slug', 'location', 'event_date', 'total_capacity', 'tickets_sold', 'is_sold_out', 'tickets_remaining']
        read_only_fields = ['id', 'slug', 'tickets_sold', 'is_sold_out', 'tickets_remaining']


class EventSerializer(serializers.ModelSerializer):
    is_sold_out = serializers.BooleanField(read_only=True)
    tickets_remaining = serializers.IntegerField(read_only=True)
    occupancy_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'slug',
            'description',
            'location',
            'event_date',
            'total_capacity',
            'tickets_sold',
            'created_at',
            'is_sold_out',
            'tickets_remaining',
            'occupancy_percentage',
        ]
        read_only_fields = ['id', 'slug', 'tickets_sold', 'created_at', 'is_sold_out', 'tickets_remaining', 'occupancy_percentage']

    def validate_total_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Total capacity must be at least 1.")
        return value


class TicketSerializer(serializers.ModelSerializer):
    event = EventSimpleSerializer(read_only=True)
    attendee = AttendeeSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ['ticket_code', 'event', 'attendee', 'booked_at']
        read_only_fields = ['ticket_code', 'event', 'attendee', 'booked_at']


class BookingRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=True, trim_whitespace=True)
    email = serializers.EmailField(required=True)


class ConcurrencySimulationSerializer(serializers.Serializer):
    event_id = serializers.IntegerField(required=True)
    num_requests = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)


class CapacityResetSerializer(serializers.Serializer):
    event_id = serializers.IntegerField(required=True)
    new_capacity = serializers.IntegerField(required=False, min_value=1)
    reset_sold_to_zero = serializers.BooleanField(required=False, default=True)
