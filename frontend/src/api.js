import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
})

export function extractErrorMessage(error, fallbackMessage) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail && typeof detail === 'object') {
    const message = typeof detail.message === 'string' ? detail.message : ''
    const errors = Array.isArray(detail.errors) ? detail.errors.filter(Boolean).join(', ') : ''
    const warnings = Array.isArray(detail.warnings) ? detail.warnings.filter(Boolean).join(', ') : ''
    return [message, errors, warnings].filter(Boolean).join(' — ') || fallbackMessage
  }
  return error?.message || fallbackMessage
}

export async function getDashboardAuthStatus() {
  const response = await apiClient.get('/auth/dashboard/status')
  return response.data
}

export async function loginDashboard(password) {
  const response = await apiClient.post('/auth/dashboard/login', { password })
  return response.data
}

export async function logoutDashboard() {
  const response = await apiClient.post('/auth/dashboard/logout')
  return response.data
}

export async function getLeads(params) {
  const response = await apiClient.get('/leads', { params })
  return response.data
}

export async function getManagerStatus() {
  const response = await apiClient.get('/manager-status')
  return response.data
}

export async function uploadLeads(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post('/upload', formData)
  return response.data
}

export async function startCampaign() {
  const response = await apiClient.post('/start-campaign')
  return response.data
}

export async function markCallCompleted(callId) {
  const response = await apiClient.post(`/test/mark-call-completed/${callId}`)
  return response.data
}

export async function markLeadDoNotContact(leadId, reason) {
  const response = await apiClient.post(`/leads/${leadId}/do-not-contact`, { reason })
  return response.data
}

export async function deleteLead(leadId) {
  const response = await apiClient.delete(`/leads/${leadId}`)
  return response.data
}
