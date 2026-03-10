import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

vi.mock('../api', () => ({
  deleteLead: vi.fn(),
  extractErrorMessage: vi.fn((error, fallback) => {
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (detail && typeof detail === 'object') {
      const message = typeof detail.message === 'string' ? detail.message : ''
      const errors = Array.isArray(detail.errors) ? detail.errors.filter(Boolean).join(', ') : ''
      const warnings = Array.isArray(detail.warnings) ? detail.warnings.filter(Boolean).join(', ') : ''
      return [message, errors, warnings].filter(Boolean).join(' — ') || fallback
    }
    return error?.message || fallback
  }),
  getDashboardAuthStatus: vi.fn(),
  getLeads: vi.fn(),
  getManagerStatus: vi.fn(),
  loginDashboard: vi.fn(),
  logoutDashboard: vi.fn(),
  markCallCompleted: vi.fn(),
  markLeadDoNotContact: vi.fn(),
  startCampaign: vi.fn(),
  uploadLeads: vi.fn(),
}))

import App from '../App'
import {
  deleteLead,
  getDashboardAuthStatus,
  getLeads,
  getManagerStatus,
  loginDashboard,
  markLeadDoNotContact,
  startCampaign,
  uploadLeads,
} from '../api'

const buildLeadsPayload = (items) => ({
  items,
  total: items.length,
  limit: 25,
  offset: 0,
  stats: {
    pending: items.filter((item) => item.status === 'pending').length,
    queued: items.filter((item) => item.status === 'queued').length,
    calling: items.filter((item) => item.status === 'calling').length,
    completed: items.filter((item) => item.status === 'completed').length,
    failed: items.filter((item) => item.status === 'failed').length,
    voicemail: items.filter((item) => item.status === 'voicemail').length,
    dnc: items.filter((item) => item.status === 'dnc').length,
  },
})

const MOCK_LEADS = buildLeadsPayload([
  {
    id: 1,
    name: 'Amit',
    phone: '+919876543210',
    status: 'completed',
    interest_level: 'high',
    contact_outcome: 'qualified',
    location: 'Bandra',
    summary: 'Interested in 2BHK',
    do_not_contact: false,
    call_id: 'call-1',
  },
  {
    id: 2,
    name: 'Priya',
    phone: '+919988776655',
    status: 'pending',
    interest_level: null,
    contact_outcome: null,
    location: null,
    summary: null,
    do_not_contact: false,
    call_id: null,
  },
])

describe('App', () => {
  beforeEach(() => {
    getDashboardAuthStatus.mockResolvedValue({ auth_required: false, authenticated: true })
    getLeads.mockResolvedValue(buildLeadsPayload([]))
    getManagerStatus.mockResolvedValue({ connected: true, join_code: 'join abc', sandbox_number: 'whatsapp:+14155238886' })
    uploadLeads.mockResolvedValue({ message: 'Uploaded 1 leads', created: 1, skipped: 0 })
    startCampaign.mockResolvedValue({ message: 'Queued 1 calls', queued: 1 })
    loginDashboard.mockResolvedValue({ authenticated: true, auth_required: true })
    markLeadDoNotContact.mockResolvedValue({ status: 'ok' })
    deleteLead.mockResolvedValue({ message: 'Deleted lead Amit' })
    vi.spyOn(window, 'prompt').mockReturnValue('requested opt out')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders dashboard shell and manager status', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Parmar Properties AI Agent')).toBeInTheDocument()
    })

    expect(screen.getByText(/WhatsApp:/)).toBeInTheDocument()
  })

  it('shows loading spinner initially', () => {
    getDashboardAuthStatus.mockImplementation(() => new Promise(() => {}))
    render(<App />)
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
  })

  it('uploads file and refreshes leads', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Parmar Properties AI Agent')).toBeInTheDocument()
    })

    const file = new File(['Name,Phone\nAmit,+919876543210\n'], 'leads.csv', { type: 'text/csv' })
    const input = screen.getByLabelText('Upload Leads CSV')
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: /Upload/i }))

    await waitFor(() => {
      expect(uploadLeads).toHaveBeenCalledWith(file)
    })
  })

  it('renders lead table with all columns', async () => {
    getLeads.mockResolvedValue(MOCK_LEADS)
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Amit')).toBeInTheDocument()
    })

      expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'Phone' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'Location' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'Interest' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'Outcome' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.getByText('qualified')).toBeInTheDocument()
  })

  it('shows empty state when no leads', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('No leads uploaded yet.')).toBeInTheDocument()
    })
  })

  it('shows auth gate and signs in when auth is required', async () => {
    getDashboardAuthStatus.mockResolvedValue({ auth_required: true, authenticated: false })
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Dashboard login required')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'super-secret' } })
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))

    await waitFor(() => {
      expect(loginDashboard).toHaveBeenCalledWith('super-secret')
    })
  })

  it('shows backend error details for failed campaign start', async () => {
    getLeads.mockResolvedValue(buildLeadsPayload([
      { id: 1, name: 'Pending', phone: '+919900000001', status: 'pending', interest_level: null, contact_outcome: null, location: null, summary: null, do_not_contact: false, call_id: null },
    ]))
    startCampaign.mockRejectedValue({ response: { data: { detail: { message: 'Vapi preflight failed', errors: ['assistant_server_missing'] } } } })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Start Campaign/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Start Campaign/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Vapi preflight failed')
      expect(screen.getByRole('alert')).toHaveTextContent('assistant_server_missing')
    })
  })

  it('opens do-not-contact action for a lead', async () => {
    getLeads.mockResolvedValue(MOCK_LEADS)
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Amit')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Mark Amit as do not contact/i }))

    await waitFor(() => {
      expect(markLeadDoNotContact).toHaveBeenCalledWith(1, 'requested opt out')
    })
  })

  it('deletes a processed lead so it can be re-uploaded', async () => {
    getLeads.mockResolvedValue(MOCK_LEADS)
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Amit')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Delete Amit/i }))

    await waitFor(() => {
      expect(deleteLead).toHaveBeenCalledWith(1)
    })
  })

  it('shows total leads count from paginated payload', async () => {
    getLeads.mockResolvedValue(MOCK_LEADS)
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/Showing 2 of 2 leads/)).toBeInTheDocument()
    })
  })
})
