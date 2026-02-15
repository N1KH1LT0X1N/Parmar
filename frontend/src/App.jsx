import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { MessageCircle, Play, Upload } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function statusClass(status) {
  return `status-chip status-${status || 'pending'}`
}

export default function App() {
  const [leads, setLeads] = useState([])
  const [file, setFile] = useState(null)
  const [managerStatus, setManagerStatus] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const leadStats = useMemo(() => {
    const counts = { pending: 0, queued: 0, calling: 0, completed: 0, failed: 0, voicemail: 0 }
    for (const lead of leads) {
      if (counts[lead.status] !== undefined) counts[lead.status] += 1
    }
    return counts
  }, [leads])

  async function fetchLeads() {
    const response = await axios.get(`${API_URL}/leads`)
    setLeads(response.data)
  }

  async function fetchManagerStatus() {
    const response = await axios.get(`${API_URL}/manager-status`)
    setManagerStatus(response.data)
  }

  async function handleUpload() {
    if (!file) return
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await axios.post(`${API_URL}/upload`, formData)
      setMessage(response.data.message)
      await fetchLeads()
    } catch (uploadError) {
      setError(uploadError?.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  async function startCampaign() {
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const response = await axios.post(`${API_URL}/start-campaign`)
      setMessage(response.data.message)
      await fetchLeads()
    } catch {
      setError('Failed to start campaign')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeads().catch(() => setError('Backend not reachable'))
    fetchManagerStatus().catch(() => setError('Backend not reachable'))

    const interval = setInterval(() => {
      fetchLeads().catch(() => undefined)
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="app-shell">
      <div className="container">
        <div className="header">
          <div>
            <h1>Parmar Properties AI Agent</h1>
            <p className="muted">Phase 2 Dashboard: upload leads, start campaign, monitor statuses live.</p>
          </div>
          {managerStatus && (
            <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <MessageCircle size={18} />
              <div>
                <div><strong>WhatsApp:</strong> {managerStatus.connected ? 'Configured' : 'Not configured'}</div>
                <div className="muted">Join code: {managerStatus.join_code || '-'}</div>
              </div>
            </div>
          )}
        </div>

        <div className="card" style={{ marginBottom: 16, background: '#fff7ed', borderColor: '#fed7aa' }}>
          <strong>Trial Mode Notice:</strong>{' '}
          If your Twilio account is in trial mode, calls may play a verification prompt like
          "This is a trial account, press any number" before connecting. Press any key to continue the call.
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="controls">
            <input
              aria-label="Upload Leads CSV"
              type="file"
              accept=".csv"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <button className="secondary" onClick={handleUpload} disabled={!file || loading}>
              <Upload size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Upload
            </button>
            <button className="primary" onClick={startCampaign} disabled={loading}>
              <Play size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Start Campaign
            </button>
          </div>

          {message ? <p className="success">{message}</p> : null}
          {error ? <p className="error">{error}</p> : null}

          <div className="muted">
            Pending: {leadStats.pending} | Queued: {leadStats.queued} | Calling: {leadStats.calling} | Completed: {leadStats.completed} | Failed: {leadStats.failed} | Voicemail: {leadStats.voicemail}
          </div>
        </div>

        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Status</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">No leads uploaded yet.</td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr key={lead.id}>
                    <td>{lead.name}</td>
                    <td>{lead.phone}</td>
                    <td><span className={statusClass(lead.status)}>{lead.status}</span></td>
                    <td>{lead.summary || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
