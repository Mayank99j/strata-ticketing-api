from django.contrib import admin
from django.utils.html import format_html
from django.db.models import F
from .models import Event, Attendee, Ticket

admin.site.site_header = "Strata Ticketing Administration"
admin.site.site_title = "Strata Admin Portal"
admin.site.index_title = "Ticketing Platform Overview & Metrics"


class SoldOutFilter(admin.SimpleListFilter):
    title = 'Availability Status'
    parameter_name = 'availability'

    def lookups(self, request, model_admin):
        return (
            ('available', 'Seats Available'),
            ('sold_out', 'Completely Sold Out'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'sold_out':
            return queryset.filter(tickets_sold__gte=F('total_capacity'))
        if self.value() == 'available':
            return queryset.filter(tickets_sold__lt=F('total_capacity'))
        return queryset


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'location',
        'event_date',
        'capacity_display',
        'occupancy_badge',
        'status_badge',
        'created_at',
    )
    list_filter = (SoldOutFilter, 'event_date')
    search_fields = ('title', 'location', 'description', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('tickets_sold', 'created_at', 'tickets_remaining_display', 'occupancy_bar_display')
    actions = ['reset_event_tickets', 'increase_capacity_10']

    fieldsets = (
        ('Event Details', {
            'fields': ('title', 'slug', 'description', 'location', 'event_date')
        }),
        ('Capacity & Inventory', {
            'fields': ('total_capacity', 'tickets_sold', 'tickets_remaining_display', 'occupancy_bar_display')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Capacity (Sold / Total)')
    def capacity_display(self, obj):
        return format_html(
            '<span style="font-variant-numeric: tabular-nums; font-weight: 600; color: #0F172A;">'
            '{} / {}</span> '
            '<span style="color: #64748B; font-size: 11px;">({} left)</span>',
            obj.tickets_sold,
            obj.total_capacity,
            obj.tickets_remaining,
        )

    @admin.display(description='Occupancy')
    def occupancy_badge(self, obj):
        pct = obj.occupancy_percentage
        color = "#1D4ED8" if pct < 80 else ("#D97706" if pct < 100 else "#DC2626")
        return format_html(
            '<div style="min-width: 90px;">'
            '  <div style="font-size: 11px; font-weight: 600; color: {0};">{1}%</div>'
            '  <div style="width: 100%; height: 6px; background: #E2E8F0; border-radius: 3px; overflow: hidden; margin-top: 2px;">'
            '    <div style="width: {1}%; height: 100%; background: {0};"></div>'
            '  </div>'
            '</div>',
            color,
            min(100.0, pct),
        )

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.is_sold_out:
            return format_html(
                '<span style="background: #F1F5F9; color: #475569; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #CBD5E1;">SOLD OUT</span>'
            )
        elif obj.tickets_remaining <= 5:
            return format_html(
                '<span style="background: #FEF3C7; color: #92400E; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #FCD34D;">FEW LEFT</span>'
            )
        else:
            return format_html(
                '<span style="background: #EFF6FF; color: #1D4ED8; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #BFDBFE;">AVAILABLE</span>'
            )

    @admin.display(description='Remaining Tickets')
    def tickets_remaining_display(self, obj):
        return f"{obj.tickets_remaining} tickets"

    @admin.display(description='Occupancy Progress')
    def occupancy_bar_display(self, obj):
        return self.occupancy_badge(obj)

    @admin.action(description="Reset tickets sold to 0 (clears tickets for selected events)")
    def reset_event_tickets(self, request, queryset):
        for event in queryset:
            event.tickets.all().delete()
            event.tickets_sold = 0
            event.save(update_fields=['tickets_sold'])
        self.message_user(request, f"Successfully reset ticket counters and cleared tickets for {queryset.count()} events.")

    @admin.action(description="Add +10 capacity to selected events")
    def increase_capacity_10(self, request, queryset):
        for event in queryset:
            event.total_capacity += 10
            event.save(update_fields=['total_capacity'])
        self.message_user(request, f"Increased capacity by +10 for {queryset.count()} events.")


@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'ticket_count', 'created_at')
    search_fields = ('name', 'email')
    readonly_fields = ('created_at',)

    @admin.display(description='Tickets Purchased')
    def ticket_count(self, obj):
        count = obj.tickets.count()
        return format_html(
            '<span style="font-weight: 600; color: #0F172A;">{}</span>',
            count
        )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_code_short', 'event', 'attendee_name', 'attendee_email', 'booked_at')
    list_filter = ('event', 'booked_at')
    search_fields = ('ticket_code', 'attendee__name', 'attendee__email', 'event__title')
    readonly_fields = ('ticket_code', 'event', 'attendee', 'booked_at')

    @admin.display(description='Ticket Code')
    def ticket_code_short(self, obj):
        return format_html(
            '<code style="font-family: monospace; font-size: 12px; background: #F1F5F9; padding: 2px 6px; border-radius: 4px; color: #0F172A;">{}</code>',
            obj.ticket_code
        )

    @admin.display(description='Attendee')
    def attendee_name(self, obj):
        return obj.attendee.name

    @admin.display(description='Attendee Email')
    def attendee_email(self, obj):
        return obj.attendee.email
