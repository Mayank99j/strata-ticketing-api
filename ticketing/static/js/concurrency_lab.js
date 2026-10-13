/**
 * Strata Event Ticketing Platform - Concurrency Lab Simulator
 */

document.addEventListener('DOMContentLoaded', () => {
  const eventSelect = document.getElementById('labEventSelect');
  const requestCountInput = document.getElementById('labRequestCount');
  const runBtn = document.getElementById('runStressTestBtn');
  const resetBtn = document.getElementById('resetEventBtn');
  const resultsContainer = document.getElementById('labResultsContainer');
  const emptyState = document.getElementById('labEmptyState');
  const loadingState = document.getElementById('labLoadingState');

  // Metric displays
  const metricVerdict = document.getElementById('metricVerdict');
  const metricCapacity = document.getElementById('metricCapacity');
  const metricInitialSold = document.getElementById('metricInitialSold');
  const metricInitialRemaining = document.getElementById('metricInitialRemaining');
  const metricSuccess = document.getElementById('metricSuccess');
  const metricSoldOut = document.getElementById('metricSoldOut');
  const metricFinalSold = document.getElementById('metricFinalSold');
  const metricDuration = document.getElementById('metricDuration');
  const threadTableBody = document.getElementById('threadTableBody');

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

  // Run Concurrency Stress Test
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const eventId = parseInt(eventSelect.value, 10);
      const numRequests = parseInt(requestCountInput.value, 10) || 10;

      if (!eventId) {
        alert('Please select an event to test.');
        return;
      }

      runBtn.disabled = true;
      runBtn.textContent = 'Executing Concurrent Transactions...';
      if (resetBtn) resetBtn.disabled = true;

      if (emptyState) emptyState.style.display = 'none';
      if (resultsContainer) resultsContainer.style.display = 'none';
      if (loadingState) loadingState.style.display = 'block';

      try {
        const response = await fetch('/api/concurrency/simulate/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || '',
          },
          body: JSON.stringify({
            event_id: eventId,
            num_requests: numRequests,
          }),
        });

        const data = await response.json();

        if (loadingState) loadingState.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        renderSimulationResults(data);
      } catch (err) {
        if (loadingState) loadingState.style.display = 'none';
        alert('Simulation failed: ' + err.message);
      } finally {
        runBtn.disabled = false;
        runBtn.textContent = 'Execute Concurrent Race Test';
        if (resetBtn) resetBtn.disabled = false;
      }
    });
  }

  // Reset Event Capacity
  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      const eventId = parseInt(eventSelect.value, 10);
      if (!eventId) return;

      if (!confirm('This will wipe test tickets for this event and reset tickets sold to 0. Proceed?')) {
        return;
      }

      resetBtn.disabled = true;
      resetBtn.textContent = 'Resetting...';

      try {
        const response = await fetch(`/api/events/${eventId}/reset/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || '',
          },
          body: JSON.stringify({ reset_sold: true }),
        });

        if (response.ok) {
          alert('Event reset successfully! Capacity is now fully available.');
          window.location.reload();
        } else {
          alert('Failed to reset event.');
        }
      } catch (err) {
        alert('Error: ' + err.message);
      } finally {
        resetBtn.disabled = false;
        resetBtn.textContent = 'Reset Event Capacity';
      }
    });
  }

  function renderSimulationResults(data) {
    // Top banner
    if (metricVerdict) {
      if (data.concurrency_safe && !data.oversold) {
        metricVerdict.className = 'notice-box';
        metricVerdict.style.borderLeftColor = '#15803D';
        metricVerdict.innerHTML = `
          <div class="notice-title" style="color: #15803D;">
            <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
            Zero Overselling Verified (100% Concurrency Safe)
          </div>
          <div class="notice-body">
            Simulated <strong>${data.num_concurrent_requests} concurrent threads</strong> at the exact same millisecond.
            Exactly <strong>${data.successful_bookings} bookings</strong> succeeded (filling remaining capacity), and
            <strong>${data.sold_out_rejections} requests</strong> were safely rejected with <code class="notice-code">400 Bad Request (Sold Out)</code>.
            Final tickets sold: <strong>${data.final_sold} / ${data.total_capacity}</strong>. Row lock prevented any overselling.
          </div>
        `;
      } else {
        metricVerdict.className = 'notice-box';
        metricVerdict.style.borderLeftColor = '#B91C1C';
        metricVerdict.innerHTML = `
          <div class="notice-title" style="color: #B91C1C;">
            Race Condition / Oversell Detected!
          </div>
          <div class="notice-body">
            Capacity was exceeded! Total sold: ${data.final_sold} vs Capacity: ${data.total_capacity}.
          </div>
        `;
      }
    }

    if (metricCapacity) metricCapacity.textContent = data.total_capacity;
    if (metricInitialSold) metricInitialSold.textContent = data.initial_sold;
    if (metricInitialRemaining) metricInitialRemaining.textContent = data.initial_remaining;
    if (metricSuccess) metricSuccess.textContent = data.successful_bookings;
    if (metricSoldOut) metricSoldOut.textContent = data.sold_out_rejections;
    if (metricFinalSold) metricFinalSold.textContent = `${data.final_sold} / ${data.total_capacity}`;
    if (metricDuration) metricDuration.textContent = `${data.overall_duration_ms} ms`;

    // Thread table
    if (threadTableBody) {
      threadTableBody.innerHTML = '';
      data.thread_results.forEach(tr => {
        const row = document.createElement('tr');
        const isSuccess = tr.status === 'SUCCESS';
        const badgeClass = isSuccess ? 'badge-available' : 'badge-soldout';
        const codeDisplay = tr.ticket_code ? `<code>${tr.ticket_code.substring(0, 8)}...</code>` : '<span style="color: #94A3B8;">&mdash;</span>';

        row.innerHTML = `
          <td><strong>#${tr.thread_index}</strong></td>
          <td><span class="badge ${badgeClass}">${tr.http_status} ${tr.status}</span></td>
          <td class="tabular">${tr.latency_ms} ms</td>
          <td>${codeDisplay}</td>
          <td>${tr.message}</td>
        `;
        threadTableBody.appendChild(row);
      });
    }
  }
});
