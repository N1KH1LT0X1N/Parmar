import { useEffect, useMemo, useCallback, useRef, useState } from 'react'
import axios from 'axios'
import { MessageCircle, Play, Upload, RefreshCw } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function statusClass(status) {
  return `status-chip status-${status || 'pending'}`
}

function interestClass(level) {
  if (!level) return 'interest-chip interest-unknown'
  return `interest-chip interest-${level}`
}

export default function App() {
  const [leads, setLeads] = useState([])
  const [file, setFile] = useState(null)
  const [managerStatus, setManagerStatus] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [backendReachable, setBackendReachable] = useState(true)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const fileInputRef = useRef(null)

  const leadStats = useMemo(() => {
    const counts = { pending: 0, queued: 0, calling: 0, completed: 0, failed: 0, voicemail: 0 }
    for (const lead of leads) {
      if (counts[lead.status] !== undefined) counts[lead.status] += 1
    }
    return counts
  }, [leads])

  const hasActiveCampaign = useMemo(
    () => leadStats.queued > 0 || leadStats.calling > 0,
    [leadStats],
  )

  const fetchLeads = useCallback(async () => {
    const response = await axios.get(`${API_URL}/leads`)
    setLeads(response.data)
    setBackendReachable(true)
  }, [])

  const fetchManagerStatus = useCallback(async () => {
    const response = await axios.get(`${API_URL}/manager-status`)
    setManagerStatus(response.data)
    setBackendReachable(true)
  }, [])

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
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await fetchLeads()
    } catch (uploadError) {
      setError(uploadError?.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  async function startCampaign() {
    if (leadStats.pending === 0) {
      setError('No pending leads to start a campaign')
      return
    }
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

  async function handleMarkCallCompleted(lead) {
    if (!lead.call_id) {
      setError('No call ID for this lead')
      return
    }
    try {
      await axios.post(`${API_URL}/test/mark-call-completed/${lead.call_id}`)
      setMessage(`Call for ${lead.name} marked as completed`)
      await fetchLeads()
    } catch (err) {
      setError(`Failed to mark call completed: ${err.response?.data?.detail || err.message}`)
    }
  }

  useEffect(() => {
    Promise.all([fetchLeads(), fetchManagerStatus()])
      .then(() => setBackendReachable(true))
      .catch(() => setBackendReachable(false))
      .finally(() => setInitialLoading(false))

    const interval = setInterval(() => {
      fetchLeads().catch(() => setBackendReachable(false))
    }, 2000)

    return () => clearInterval(interval)
  }, [fetchLeads, fetchManagerStatus])

  if (initialLoading) {
    return (
      <div className="app-shell">
        <div className="container" style={{ textAlign: 'center', paddingTop: 80 }}>
          <RefreshCw size={32} className="spin" />
          <p className="muted" style={{ marginTop: 12 }}>Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <div className="container">
        <div className="header">
          <div>
            <h1>Parmar Properties AI Agent</h1>
            <p className="muted">Upload leads, start campaign, monitor statuses live.</p>
          </div>
          {managerStatus && (
            <div className="card manager-card">
              <MessageCircle size={18} />
              <div>
                <div><strong>WhatsApp:</strong> {managerStatus.connected ? '✅ Configured' : '❌ Not configured'}</div>
                <div className="muted">Join code: {managerStatus.join_code || '-'}</div>
              </div>
            </div>
          )}
        </div>

        <div className="card notice-card">
          <strong>Trial Mode Notice:</strong>{' '}
          If your Twilio account is in trial mode, calls may play a verification prompt like
          "This is a trial account, press any number" before connecting. Press any key to continue the call.
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="controls">
            <input
              ref={fileInputRef}
              aria-label="Upload Leads CSV"
              type="file"
              accept=".csv"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <button className="secondary" onClick={handleUpload} disabled={!file || loading}>
              <Upload size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Upload
            </button>
            <button className="primary" onClick={startCampaign} disabled={loading || hasActiveCampaign || leadStats.pending === 0}>
              <Play size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
              {hasActiveCampaign ? 'Campaign Running...' : 'Start Campaign'}
            </button>
          </div>

          {message ? <p className="success">{message}</p> : null}
          {!backendReachable ? <p className="error">Backend not reachable</p> : null}
          {backendReachable && error ? <p className="error">{error}</p> : null}

          <div className="stats-bar">
            <span className="stat stat-pending">Pending: {leadStats.pending}</span>
            <span className="stat stat-queued">Queued: {leadStats.queued}</span>
            <span className="stat stat-calling">Calling: {leadStats.calling}</span>
            <span className="stat stat-completed">Completed: {leadStats.completed}</span>
            <span className="stat stat-failed">Failed: {leadStats.failed}</span>
            <span className="stat stat-voicemail">VM: {leadStats.voicemail}</span>
          </div>
        </div>

        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Location</th>
                <th>Status</th>
                <th>Interest</th>
                <th>Summary</th>
                <th style={{ width: 120 }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted">No leads uploaded yet.</td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr key={lead.id}>
                    <td>{lead.name}</td>
                    <td className="phone-cell">{lead.phone}</td>
                    <td>{lead.location || '-'}</td>
                    <td><span className={statusClass(lead.status)}>{lead.status}</span></td>
                    <td><span className={interestClass(lead.interest_level)}>{lead.interest_level || '-'}</span></td>
                    <td className="summary-cell">{lead.summary || '-'}</td>
                    <td style={{ textAlign: 'center' }}>
                      {lead.status === 'calling' && lead.call_id && (
                        <button 
                          className="action-btn"
                          onClick={() => handleMarkCallCompleted(lead)}
                          title="Complete the ongoing call (for testing)"
                        >
                          End Call
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <p className="muted" style={{ textAlign: 'center', marginTop: 12 }}>
          Total leads: {leads.length} · Auto-refreshing every 2s
        </p>
      </div>
    </div>
  )
}
