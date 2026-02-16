import { useEffect, useMemo, useCallback, useRef, useState } from 'react'
import axios from 'axios'
import { MessageCircle, Play, Upload, RefreshCw } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const ENABLE_TEST_ENDPOINTS = import.meta.env.VITE_ENABLE_TEST_ENDPOINTS === 'true'
const DASHBOARD_API_KEY = import.meta.env.VITE_DASHBOARD_API_KEY || ''
const DASHBOARD_API_KEY_HEADER = import.meta.env.VITE_DASHBOARD_API_KEY_HEADER || 'X-API-Key'

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
  const requestConfig = useMemo(() => {
    if (!DASHBOARD_API_KEY) return undefined
    return { headers: { [DASHBOARD_API_KEY_HEADER]: DASHBOARD_API_KEY } }
  }, [])

  const leadStats = useMemo(() => {
    const counts = { pending: 0, queued: 0, calling: 0, completed: 0, failed: 0, voicemail: 0, dnc: 0 }
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
    const response = await axios.get(`${API_URL}/leads`, requestConfig)
    setLeads(response.data)
    setBackendReachable(true)
  }, [requestConfig])

  const fetchManagerStatus = useCallback(async () => {
    const response = await axios.get(`${API_URL}/manager-status`, requestConfig)
    setManagerStatus(response.data)
    setBackendReachable(true)
  }, [requestConfig])

  async function handleUpload() {
    if (!file) return
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await axios.post(`${API_URL}/upload`, formData, requestConfig)
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
      const response = await axios.post(`${API_URL}/start-campaign`, null, requestConfig)
      setMessage(response.data.message)
      await fetchLeads()
    } catch {
      setError('Failed to start campaign')
    } finally {
      setLoading(false)
    }
  }

  async function handleMarkCallCompleted(lead) {
    if (!ENABLE_TEST_ENDPOINTS) {
      setError('Test endpoints are disabled for this environment')
      return
    }
    if (!lead.call_id) {
      setError('No call ID for this lead')
      return
    }
    try {
      await axios.post(`${API_URL}/test/mark-call-completed/${lead.call_id}`, null, requestConfig)
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
        <main className="container" aria-busy="true">
          <div className="loading-state" style={{ textAlign: 'center', paddingTop: 80 }}>
            <RefreshCw size={32} className="spin" aria-hidden="true" />
            <p className="muted" style={{ marginTop: 12 }} role="status" aria-live="polite">
              Loading dashboard...
            </p>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="container">
        <div className="header">
          <div>
            <h1>Parmar Properties AI Agent</h1>
            <p className="muted">Upload leads, start campaign, monitor statuses live.</p>
          </div>
          {managerStatus && (
            <section className="card manager-card" aria-label="Manager WhatsApp status">
              <MessageCircle size={18} aria-hidden="true" />
              <div>
                <div><strong>WhatsApp:</strong> {managerStatus.connected ? 'Configured' : 'Not configured'}</div>
                <div className="muted">Join code: {managerStatus.join_code || '-'}</div>
              </div>
            </section>
          )}
        </div>
      </header>

      <main className="container" aria-busy={loading}>
        <div aria-live="polite" role="status" className="sr-only">
          {message || (!backendReachable ? 'Connection problem: backend not reachable' : (error ? `Error: ${error}` : ''))}
        </div>

        <div className="card notice-card">
          <strong>Trial Mode Notice:</strong>{' '}
          If your Twilio account is in trial mode, calls may play a verification prompt like
          "This is a trial account, press any number" before connecting. Press any key to continue the call.
        </div>

        <section className="card" style={{ marginBottom: 16 }} aria-label="Campaign controls">
          <div className="controls">
            <label htmlFor="lead-upload-input" className="sr-only">Upload Leads CSV</label>
            <input
              id="lead-upload-input"
              ref={fileInputRef}
              aria-label="Upload Leads CSV"
              type="file"
              accept=".csv"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <button className="secondary" onClick={handleUpload} disabled={!file || loading}>
              <Upload size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" /> Upload
            </button>
            <button
              className="primary"
              onClick={startCampaign}
              disabled={loading || hasActiveCampaign || leadStats.pending === 0}
            >
              <Play size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" />
              {hasActiveCampaign ? 'Campaign Running...' : 'Start Campaign'}
            </button>
          </div>

          {message ? <p className="success" role="status" aria-live="polite">{message}</p> : null}
          {!backendReachable ? <p className="error" role="alert">Backend not reachable</p> : null}
          {backendReachable && error ? <p className="error" role="alert">{error}</p> : null}

          <div className="stats-bar" aria-label="Lead status summary">
            <span className="stat stat-pending">Pending: {leadStats.pending}</span>
            <span className="stat stat-queued">Queued: {leadStats.queued}</span>
            <span className="stat stat-calling">Calling: {leadStats.calling}</span>
            <span className="stat stat-completed">Completed: {leadStats.completed}</span>
            <span className="stat stat-failed">Failed: {leadStats.failed}</span>
            <span className="stat stat-voicemail">VM: {leadStats.voicemail}</span>
            <span className="stat stat-dnc">DNC: {leadStats.dnc}</span>
          </div>
        </section>

        <section className="card table-wrap" aria-label="Lead table">
          <table>
            <caption className="sr-only">Leads and call outcomes</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Phone</th>
                <th scope="col">Location</th>
                <th scope="col">Status</th>
                <th scope="col">Interest</th>
                <th scope="col">Summary</th>
                <th scope="col" style={{ width: 120 }}>Action</th>
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
                      {ENABLE_TEST_ENDPOINTS && lead.status === 'calling' && lead.call_id && (
                        <button
                          className="action-btn"
                          onClick={() => handleMarkCallCompleted(lead)}
                          title="Complete the ongoing call (for testing)"
                          aria-label={`End call for ${lead.name}`}
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
        </section>

        <p className="muted" style={{ textAlign: 'center', marginTop: 12 }}>
          Total leads: {leads.length} - Auto-refreshing every 2s
        </p>
      </main>
    </div>
  )
}
