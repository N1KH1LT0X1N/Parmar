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

describe('App', () => {
  beforeEach(() => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/leads')) return Promise.resolve({ data: [] })
      if (url.includes('/manager-status')) {
        return Promise.resolve({ data: { connected: true, join_code: 'join abc', sandbox_number: 'whatsapp:+14155238886' } })
      }
      return Promise.resolve({ data: {} })
    })
    axios.post.mockResolvedValue({ data: { message: 'ok' } })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders dashboard shell and manager status', async () => {
    render(<App />)
    expect(screen.getByText('Parmar Properties AI Agent')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/WhatsApp:/)).toBeInTheDocument()
    })
  })

  it('uploads file and starts campaign', async () => {
    render(<App />)

    const file = new File(['Name,Phone\nAmit,+919876543210\n'], 'leads.csv', { type: 'text/csv' })
    const input = screen.getByLabelText('Upload Leads CSV')
    fireEvent.change(input, { target: { files: [file] } })

    const uploadButton = screen.getByRole('button', { name: /Upload/i })
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(expect.stringContaining('/upload'), expect.any(FormData))
    })

    const startButton = screen.getByRole('button', { name: /Start Campaign/i })
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(expect.stringContaining('/start-campaign'))
    })
  })
})
