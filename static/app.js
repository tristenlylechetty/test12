let geo = null;
let selectedSlot = null;

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

function slotLabel(slot) {
  const start = new Date(slot.starts_at).toLocaleString();
  const end = new Date(slot.ends_at).toLocaleTimeString();
  return `${start} - ${end}`;
}

async function loadConfig() {
  const cfg = await fetchJSON('/api/config');
  const regionSel = document.getElementById('region');
  cfg.regions.forEach((r) => {
    const opt = document.createElement('option');
    opt.value = r;
    opt.textContent = r;
    regionSel.appendChild(opt);
  });
  document.getElementById('date').value = new Date().toISOString().slice(0, 10);
}

function renderSlots(slots) {
  const wrap = document.getElementById('slots');
  wrap.innerHTML = '';
  selectedSlot = null;

  if (!slots.length) {
    wrap.textContent = 'No suitable slots found. Try another date or region.';
    return;
  }

  slots.forEach((slot) => {
    const div = document.createElement('div');
    div.className = 'slot';
    div.innerHTML = `
      <div>
        <strong>${slot.agent_name}</strong> (${slot.region})<br>
        ${slotLabel(slot)}
      </div>
      <div>
        Travel: ${slot.travel_minutes} min<br>
        Score: ${slot.score}
      </div>
    `;
    div.onclick = () => {
      document.querySelectorAll('.slot').forEach((n) => n.classList.remove('selected'));
      div.classList.add('selected');
      selectedSlot = slot;
    };
    wrap.appendChild(div);
  });
}

document.getElementById('geocodeBtn').onclick = async () => {
  try {
    const address = document.getElementById('address').value.trim();
    geo = await fetchJSON('/api/geocode', {
      method: 'POST',
      body: JSON.stringify({ address }),
    });
    document.getElementById('geoResult').textContent = `Validated (${geo.mode}): ${geo.formatted_address} [${geo.lat}, ${geo.lng}]`;
  } catch (e) {
    document.getElementById('geoResult').textContent = e.message;
  }
};

document.getElementById('suggestBtn').onclick = async () => {
  try {
    if (!geo) {
      throw new Error('Validate the address first.');
    }
    const payload = {
      region: document.getElementById('region').value,
      date: document.getElementById('date').value,
      lat: geo.lat,
      lng: geo.lng,
      duration_minutes: 60,
    };
    const result = await fetchJSON('/api/suggest-slots', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderSlots(result.slots);
  } catch (e) {
    document.getElementById('slots').textContent = e.message;
  }
};

document.getElementById('bookBtn').onclick = async () => {
  try {
    if (!selectedSlot) {
      throw new Error('Select a slot first.');
    }
    if (!geo) {
      throw new Error('Validate address first.');
    }
    const payload = {
      client_name: document.getElementById('clientName').value.trim(),
      client_phone: document.getElementById('clientPhone').value.trim(),
      address: geo.formatted_address,
      region: document.getElementById('region').value,
      lat: geo.lat,
      lng: geo.lng,
      agent_id: selectedSlot.agent_id,
      starts_at: selectedSlot.starts_at,
      ends_at: selectedSlot.ends_at,
      travel_minutes: selectedSlot.travel_minutes,
      notes: document.getElementById('notes').value.trim(),
    };
    const result = await fetchJSON('/api/book', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    document.getElementById('bookResult').textContent = `Booked successfully. Booking ID: ${result.booking_id}. Outlook mode: ${result.outlook_mode}.`;
  } catch (e) {
    document.getElementById('bookResult').textContent = e.message;
  }
};

loadConfig();
