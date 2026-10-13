import uuid
from django.db import models
from django.utils.text import slugify


class Event(models.Model):
    """
    Represents an event with a limited seating capacity.
    """
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    location = models.CharField(max_length=200)
    event_date = models.DateTimeField()
    total_capacity = models.PositiveIntegerField()
    tickets_sold = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['event_date']
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tickets_sold__lte=models.F('total_capacity')),
                name='tickets_sold_lte_capacity',
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.tickets_sold}/{self.total_capacity})"

    @property
    def is_sold_out(self) -> bool:
        """
        True when tickets_sold has reached or exceeded total_capacity.
        """
        return self.tickets_sold >= self.total_capacity

    @property
    def tickets_remaining(self) -> int:
        """
        Calculates the number of tickets still available for purchase.
        """
        return max(0, self.total_capacity - self.tickets_sold)

    @property
    def occupancy_percentage(self) -> float:
        """
        Percentage of tickets sold relative to total capacity.
        """
        if self.total_capacity == 0:
            return 100.0 if self.tickets_sold > 0 else 0.0
        return round((self.tickets_sold / self.total_capacity) * 100, 1)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "event"
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Attendee(models.Model):
    """
    Represents a ticket holder or buyer.
    """
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Attendee'
        verbose_name_plural = 'Attendees'

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Ticket(models.Model):
    """
    Represents an issued ticket for an event.
    """
    ticket_code = models.CharField(max_length=36, unique=True, blank=True)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    attendee = models.ForeignKey(
        Attendee,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-booked_at']
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'

    def __str__(self):
        return f"Ticket {self.ticket_code[:8]}... - {self.event.title} ({self.attendee.email})"

    def save(self, *args, **kwargs):
        if not self.ticket_code:
            self.ticket_code = str(uuid.uuid4())
        super().save(*args, **kwargs)
