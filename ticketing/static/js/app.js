/**
 * Strata Event Ticketing Platform - Client Application
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const searchInput = document.getElementById('eventSearchInput');
  const filterButtons = document.querySelectorAll('.filter-btn');
  const eventCards = document.querySelectorAll('.event-card');
  const bookingModal = document.getElementById('bookingModal');
  const bookingForm = document.getElementById('bookingForm');
  const modalCloseBtn = document.getElementById('modalCloseBtn');
  const modalCancelBtn = document.getElementById('modalCancelBtn');
  const bookingSubmitBtn = document.getElementById('bookingSubmitBtn');
  const formContent = document.getElementById('formContent');
  const successContent = document.getElementById('successContent');
  const bookingError = document.getElementById('bookingError');

  let activeFilter = 'all';
  let activeEventId = null;

  // --------------------------------------------------------------------------
  // 1. Search & Filtering
  // --------------------------------------------------------------------------
  function filterEvents() {
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    eventCards.forEach(card => {
      const title = (card.dataset.title || '').toLowerCase();
      const location = (card.dataset.location || '').toLowerCase();
      const isSoldOut = card.dataset.soldOut === 'true';

      let matchesFilter = true;
      if (activeFilter === 'available') {
        matchesFilter = !isSoldOut;
      } else if (activeFilter === 'sold_out') {
        matchesFilter = isSoldOut;
      }

      const matchesSearch = !query || title.includes(query) || location.includes(query);

      if (matchesFilter && matchesSearch) {
        card.style.display = 'flex';
      } else {
        card.style.display = 'none';
      }
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', filterEvents);
  }

  filterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      filterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      filterEvents();
    });
  });

  // --------------------------------------------------------------------------
  // 2. Booking Modal Controls
  // --------------------------------------------------------------------------
  window.openBookingModal = function(eventId, eventTitle, remainingSeats) {
    activeEventId = eventId;
    if (bookingError) {
      bookingError.style.display = 'none';
      bookingError.textContent = '';
    }

    // Reset views
    if (formContent) formContent.style.display = 'block';
    if (successContent) successContent.style.display = 'none';
    if (bookingSubmitBtn) {
      bookingSubmitBtn.style.display = 'inline-flex';
      bookingSubmitBtn.disabled = false;
      bookingSubmitBtn.textContent = 'Confirm Reservation';
    }

    // Set modal headers
    const modalEventTitle = document.getElementById('modalEventTitle');
    const modalRemainingSeats = document.getElementById('modalRemainingSeats');
    if (modalEventTitle) modalEventTitle.textContent = eventTitle;
    if (modalRemainingSeats) modalRemainingSeats.textContent = `${remainingSeats} seats remaining`;

    // Clear form inputs
    if (bookingForm) bookingForm.reset();

    // Show modal
    if (bookingModal) bookingModal.classList.add('active');
  };

  function closeModal() {
    if (bookingModal) bookingModal.classList.remove('active');
    activeEventId = null;
  }

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
  if (modalCancelBtn) modalCancelBtn.addEventListener('click', closeModal);

  if (bookingModal) {
    bookingModal.addEventListener('click', (e) => {
      if (e.target === bookingModal) {
        closeModal();
      }
    });
  }

  // --------------------------------------------------------------------------
  // 3. Form Submission with CSRF & Concurrency Handling
  // --------------------------------------------------------------------------
  if (bookingForm) {
    bookingForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!activeEventId) return;

      const nameInput = document.getElementById('attendeeName');
      const emailInput = document.getElementById('attendeeEmail');
      const name = nameInput.value.trim();
      const email = emailInput.value.trim();

      if (!name || !email) {
        showError('Please provide both your full name and a valid email address.');
        return;
      }

      bookingSubmitBtn.disabled = true;
      bookingSubmitBtn.textContent = 'Securing Seat...';
      if (bookingError) bookingError.style.display = 'none';

      // Read CSRF token from cookie if available
      const getCookie = (name) => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
          const cookies = document.cookie.split(';');
          for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
            }
          }
        }
        return cookieValue;
      };

      try {
        const response = await fetch(`/api/events/${activeEventId}/book/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || '',
          },
          body: JSON.stringify({ name, email }),
        });

        const data = await response.json();

        if (response.ok) {
          // Success: Display digital ticket
          renderTicketReceipt(data);
          updateCardDOM(activeEventId, data.event);
        } else {
          // Error: E.g., sold out or validation error
          const msg = data.error || (data.name ? data.name[0] : null) || (data.email ? data.email[0] : null) || 'Unable to book ticket.';
          showError(msg);
          bookingSubmitBtn.disabled = false;
          bookingSubmitBtn.textContent = 'Confirm Reservation';
        }
      } catch (err) {
        showError('Network error connecting to booking service. Please try again.');
        bookingSubmitBtn.disabled = false;
        bookingSubmitBtn.textContent = 'Confirm Reservation';
      }
    });
  }

  function showError(msg) {
    if (bookingError) {
      bookingError.textContent = msg;
      bookingError.style.display = 'block';
    }
  }

  function renderTicketReceipt(ticketData) {
    if (formContent) formContent.style.display = 'none';
    if (bookingSubmitBtn) bookingSubmitBtn.style.display = 'none';
    if (successContent) successContent.style.display = 'block';

    const rCode = document.getElementById('receiptTicketCode');
    const rName = document.getElementById('receiptAttendeeName');
    const rEmail = document.getElementById('receiptAttendeeEmail');
    const rEvent = document.getElementById('receiptEventTitle');
    const rDate = document.getElementById('receiptBookedAt');

    if (rCode) rCode.textContent = ticketData.ticket_code;
    if (rName) rName.textContent = ticketData.attendee.name;
    if (rEmail) rEmail.textContent = ticketData.attendee.email;
    if (rEvent) rEvent.textContent = ticketData.event.title;
    if (rDate) rDate.textContent = new Date(ticketData.booked_at).toLocaleString();
  }

  function updateCardDOM(eventId, eventData) {
    const card = document.querySelector(`.event-card[data-event-id="${eventId}"]`);
    if (!card || !eventData) return;

    const countElem = card.querySelector('.sold-count');
    const remainingElem = card.querySelector('.remaining-count');
    const progressBar = card.querySelector('.progress-bar');
    const actionContainer = card.querySelector('.event-card-actions');
    const badgeElem = card.querySelector('.badge');

    if (countElem) countElem.textContent = eventData.tickets_sold;
    if (remainingElem) remainingElem.textContent = `${eventData.tickets_remaining} remaining`;

    const pct = Math.min(100, Math.round((eventData.tickets_sold / eventData.total_capacity) * 100));
    if (progressBar) {
      progressBar.style.width = `${pct}%`;
      if (eventData.is_sold_out) {
        progressBar.className = 'progress-bar soldout';
      } else if (eventData.tickets_remaining <= 5) {
        progressBar.className = 'progress-bar warning';
      }
    }

    if (eventData.is_sold_out) {
      card.dataset.soldOut = 'true';
      if (badgeElem) {
        badgeElem.className = 'badge badge-soldout';
        badgeElem.textContent = 'SOLD OUT';
      }
      if (actionContainer) {
        actionContainer.innerHTML = `<button class="btn btn-disabled btn-block" disabled>Sold Out</button>`;
      }
    } else {
      if (badgeElem && eventData.tickets_remaining <= 5) {
        badgeElem.className = 'badge badge-warning';
        badgeElem.textContent = 'FEW LEFT';
      }
    }
  }

  // --------------------------------------------------------------------------
  // 4. Copy Ticket Code Helper
  // --------------------------------------------------------------------------
  window.copyTicketCode = function() {
    const rCode = document.getElementById('receiptTicketCode');
    if (!rCode) return;
    navigator.clipboard.writeText(rCode.textContent).then(() => {
      const copyBtn = document.getElementById('copyTicketBtn');
      if (copyBtn) {
        const orig = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        setTimeout(() => copyBtn.textContent = orig, 1800);
      }
    });
  };
});
