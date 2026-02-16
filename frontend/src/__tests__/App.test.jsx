import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

vi.mock('axios', () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
    },
  }
})

import axios from 'axios'
import App from '../App'

const MOCK_LEADS = [
  { id: 1, name: 'Amit', phone: '+919876543210', status: 'completed', interest_level: 'high', location: 'Bandra', summary: 'Interested in 2BHK' },
  { id: 2, name: 'Priya', phone: '+919988776655', status: 'pending', interest_level: null, location: null, summary: null },
]

describe('App', () => {
  beforeEach(() => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/leads')) return Promise.resolve({ data: [] })
      if (url.includes('/manager-status')) {
        return Promise.resolve({ data: { connected: true, join_code: 'join abc', sandbox_number: 'whatsapp:+14155238886' } })
      }
      return Promise.resolve({ data: {} })
    })
    axios.post.mockResolvedValue({ data: { message: 'ok', created: 1, skipped: 0 } })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders dashboard shell and manager status', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Parmar Properties AI Agent')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText(/WhatsApp:/)).toBeInTheDocument()
    })
  })

  it('shows loading spinner initially', () => {
    // Make API hang so initial loading stays
    axios.get.mockImplementation(() => new Promise(() => {}))
    render(<App />)
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
  })

  it('uploads file and starts campaign', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Parmar Properties AI Agent')).toBeInTheDocument()
    })

    const file = new File(['Name,Phone\nAmit,+919876543210\n'], 'leads.csv', { type: 'text/csv' })
    const input = screen.getByLabelText('Upload Leads CSV')
    fireEvent.change(input, { target: { files: [file] } })

    const uploadButton = screen.getByRole('button', { name: /Upload/i })
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalled()
    })

    const uploadCall = axios.post.mock.calls.find((args) => `${args[0]}`.includes('/upload'))
    expect(uploadCall).toBeTruthy()
    expect(uploadCall[1]).toBeInstanceOf(FormData)
  })

  it('renders lead table with all columns', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/leads')) return Promise.resolve({ data: MOCK_LEADS })
      if (url.includes('/manager-status')) {
        return Promise.resolve({ data: { connected: true, join_code: 'join abc', sandbox_number: 'whatsapp:+14155238886' } })
      }
      return Promise.resolve({ data: {} })
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Amit')).toBeInTheDocument()
    })

    // Check table headers
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Phone')).toBeInTheDocument()
    expect(screen.getByText('Location')).toBeInTheDocument()
    expect(screen.getByText('Status')).toBeInTheDocument()
    expect(screen.getByText('Interest')).toBeInTheDocument()
    expect(screen.getByText('Summary')).toBeInTheDocument()

    // Check data
    expect(screen.getByText('Amit')).toBeInTheDocument()
    expect(screen.getByText('Bandra')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
    expect(screen.getByText('Interested in 2BHK')).toBeInTheDocument()
  })

  it('shows empty state when no leads', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('No leads uploaded yet.')).toBeInTheDocument()
    })
  })

  it('shows error when backend is unreachable', async () => {
    axios.get.mockRejectedValue(new Error('Network Error'))

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Backend not reachable')).toBeInTheDocument()
    })
  })

  it('disables start campaign when no pending leads', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/leads')) return Promise.resolve({ data: [{ id: 1, name: 'A', phone: '+91x', status: 'completed' }] })
      if (url.includes('/manager-status')) return Promise.resolve({ data: { connected: false, join_code: '', sandbox_number: '' } })
      return Promise.resolve({ data: {} })
    })

    render(<App />)

    await waitFor(() => {
      const startButton = screen.getByRole('button', { name: /Start Campaign/i })
      expect(startButton).toBeDisabled()
    })
  })

  it('shows total leads count', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/leads')) return Promise.resolve({ data: MOCK_LEADS })
      if (url.includes('/manager-status')) return Promise.resolve({ data: { connected: true, join_code: '', sandbox_number: '' } })
      return Promise.resolve({ data: {} })
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/Total leads: 2/)).toBeInTheDocument()
    })
  })
})
