const API_BASE = (import.meta.env.VITE_API_BASE || '/api');

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const errorBody = await response.text().catch(() => '');
    throw new Error(`API error ${response.status}: ${errorBody || response.statusText}`);
  }

  if (response.status === 204) return null;

  return response.json();
}

// Contacts
export function getContacts(params = {}) {
  const query = new URLSearchParams();
  if (params.tier) query.set('tier', params.tier);
  if (params.domain) query.set('domain', params.domain);
  if (params.super_connector !== undefined) query.set('super_connector', params.super_connector);
  if (params.search) query.set('search', params.search);
  if (params.contact_type) query.set('contact_type', params.contact_type);
  const qs = query.toString();
  return request(`/contacts${qs ? '?' + qs : ''}`);
}

export function getContact(id) {
  return request(`/contacts/${id}`);
}

export function createContact(data) {
  return request('/contacts', { method: 'POST', body: JSON.stringify(data) });
}

export function updateContact(id, data) {
  return request(`/contacts/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function deleteContact(id) {
  return request(`/contacts/${id}`, { method: 'DELETE' });
}

export function getGoingCold() {
  return request('/contacts/going-cold');
}

export function getSuperConnectors() {
  return request('/contacts/super-connectors');
}

// Interactions
export function getInteractions(params = {}) {
  const query = new URLSearchParams();
  if (params.contact_id) query.set('contact_id', params.contact_id);
  const qs = query.toString();
  return request(`/interactions${qs ? '?' + qs : ''}`);
}

export function createInteraction(data) {
  return request('/interactions', { method: 'POST', body: JSON.stringify(data) });
}

export function getOpenLoops() {
  return request('/interactions/open-loops');
}

// Venues
export function getVenues() {
  return request('/venues');
}

export function createVenue(data) {
  return request('/venues', { method: 'POST', body: JSON.stringify(data) });
}

export function updateVenue(id, data) {
  return request(`/venues/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

// Happy Hours
export function getHappyHours() {
  return request('/happy-hours');
}

export function getHappyHour(id) {
  return request(`/happy-hours/${id}`);
}

export function createHappyHour(data) {
  return request('/happy-hours', { method: 'POST', body: JSON.stringify(data) });
}

export function updateHappyHour(id, data) {
  return request(`/happy-hours/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function addAttendee(happyHourId, data) {
  return request(`/happy-hours/${happyHourId}/attendees`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function removeAttendee(happyHourId, contactId) {
  return request(`/happy-hours/${happyHourId}/attendees/${contactId}`, {
    method: 'DELETE',
  });
}

export function updateAttendee(happyHourId, contactId, data) {
  return request(`/happy-hours/${happyHourId}/attendees/${contactId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// Intros
export function getIntros() {
  return request('/intros');
}

export function createIntro(data) {
  return request('/intros', { method: 'POST', body: JSON.stringify(data) });
}

export function updateIntro(id, data) {
  return request(`/intros/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

// Outreach
export function getCurrentOutreach() {
  return request('/outreach/current');
}

export function getProfessionalDue() {
  return request('/outreach/professional/due');
}

export function getProfessionalOutreach() {
  return request('/outreach/professional/current');
}

// Migration
export function migrateContact(id, contactType, professionalTier) {
  const params = new URLSearchParams({ contact_type: contactType });
  if (professionalTier) params.set('professional_tier', professionalTier);
  return request(`/contacts/${id}/migrate?${params}`, { method: 'PUT' });
}

// AI Generation
export function generateOutreach(force = false) {
  return request(`/outreach/generate${force ? '?force=true' : ''}`, { method: 'POST' });
}

export function generateProfessionalPulse(force = false) {
  return request(`/professional/generate${force ? '?force=true' : ''}`, { method: 'POST' });
}

export function suggestHappyHourGroup() {
  return request('/happy-hour/suggest', { method: 'POST' });
}

export function analyzeInteraction(interactionId) {
  return request(`/follow-up/analyze?interaction_id=${interactionId}`, { method: 'POST' });
}

export function triggerLinkedInScan() {
  return request('/linkedin/scan', { method: 'POST' });
}

export function scanSingleContact(contactId) {
  return request(`/linkedin/scan/${contactId}`, { method: 'POST' });
}

export function getLinkedInEvents() {
  return request('/linkedin/events');
}

export function dismissLinkedInEvent(eventId) {
  return request(`/linkedin/events/${eventId}/dismiss`, { method: 'PUT' });
}

export function suggestIntros() {
  return request('/intros/suggest', { method: 'POST' });
}

// Outreach actions
export function approveOutreach(id) {
  return request(`/outreach/${id}`, { method: 'PUT', body: JSON.stringify({ status: 'approved' }) });
}

export function skipOutreach(id) {
  return request(`/outreach/${id}`, { method: 'PUT', body: JSON.stringify({ status: 'skipped' }) });
}

export function markOutreachSent(id) {
  return request(`/outreach/${id}/send`, { method: 'PUT' });
}

// Scheduler
export function getSchedulerStatus() {
  return request('/scheduler/status');
}

export function triggerSchedulerJob(jobName) {
  return request(`/scheduler/trigger/${jobName}`, { method: 'POST' });
}

export function getNotificationLogs(limit = 50) {
  return request(`/scheduler/logs?limit=${limit}`);
}

export function getPendingCount() {
  return request('/scheduler/pending-count');
}

// Queue: get all pending/approved plans for mobile approval
export function getQueuePlans() {
  return request('/outreach/current');
}
