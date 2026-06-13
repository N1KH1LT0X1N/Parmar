import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageCircle, RefreshCw } from 'lucide-react'

import {
  deleteLead,
  extractErrorMessage,
  getDashboardAuthStatus,
  getLeads,
  getManagerStatus,
  loginDashboard,
  logoutDashboard,
  markCallCompleted,
  markLeadDoNotContact,
  startCampaign,
  uploadLeads,
} from './api'
import CampaignControls from './components/CampaignControls'
import DashboardLogin from './components/DashboardLogin'
import LeadFilters from './components/LeadFilters'
import LeadTable from './components/LeadTable'
import Pagination from './components/Pagination'

const ENABLE_TEST_ENDPOINTS = import.meta.env.VITE_ENABLE_TEST_ENDPOINTS === 'true'
const DEFAULT_LIMIT = 25

export default function App() {
  const [leadsPayload, setLeadsPayload] = useState({
    items: [],
    total: 0,
    limit: DEFAULT_LIMIT,
    offset: 0,
    stats: { pending: 0, queued: 0, calling: 0, completed: 0, failed: 0, voicemail: 0, dnc: 0 },
  })
  const [file, setFile] = useState(null)
  const [managerStatus, setManagerStatus] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [backendReachable, setBackendReachable] = useState(true)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [authRequired, setAuthRequired] = useState(false)
  const [authenticated, setAuthenticated] = useState(true)
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [activeOnly, setActiveOnly] = useState(false)
  const [offset, setOffset] = useState(0)
  const fileInputRef = useRef(null)
  const pollTickRef = useRef(0)

  const leadStats = leadsPayload.stats
  const hasActiveCampaign = useMemo(
    () => leadStats.queued > 0 || leadStats.calling > 0,
    [leadStats],
  )

  const queryParams = useMemo(() => ({
    limit: DEFAULT_LIMIT,
    offset,
    search: search || undefined,
    status: statusFilter || undefined,
    active_only: activeOnly || undefined,
  }), [activeOnly, offset, search, statusFilter])

  const fetchDashboard = useCallback(async ({ includeManager = true } = {}) => {
    const tasks = [getLeads(queryParams)]
    if (includeManager) tasks.push(getManagerStatus())

    const results = await Promise.all(tasks)
    setLeadsPayload(results[0])
    if (includeManager) setManagerStatus(results[1])
    setBackendReachable(true)
  }, [queryParams])

  const refreshAuthState = useCallback(async () => {
    const authState = await getDashboardAuthStatus()
    setAuthRequired(authState.auth_required)
    setAuthenticated(authState.authenticated)
    return authState
  }, [])

  const loadInitialData = useCallback(async () => {
    setInitialLoading(true)
    setError('')
    try {
      const authState = await refreshAuthState()
      if (authState.auth_required && !authState.authenticated) {
        setBackendReachable(true)
        return
      }
      await fetchDashboard({ includeManager: true })
    } catch (loadError) {
      if (loadError?.response?.status === 401) {
        setAuthRequired(true)
        setAuthenticated(false)
        setBackendReachable(true)
      } else {
        setBackendReachable(false)
        setError(extractErrorMessage(loadError, 'Failed to load dashboard'))
      }
    } finally {
      setInitialLoading(false)
    }
  }, [fetchDashboard, refreshAuthState])

  async function handleLogin(event) {
    event.preventDefault()
    setLoginError('')
    setLoading(true)
    try {
      await loginDashboard(password)
      setAuthenticated(true)
      setMessage('Signed in successfully')
      setPassword('')
      await fetchDashboard({ includeManager: true })
    } catch (loginAttemptError) {
      setLoginError(extractErrorMessage(loginAttemptError, 'Failed to sign in'))
    } finally {
      setLoading(false)
    }
  }

  async function handleLogout() {
    setLoading(true)
    try {
      await logoutDashboard()
      setAuthenticated(false)
      setMessage('Signed out')
      setLeadsPayload((current) => ({ ...current, items: [], total: 0 }))
    } catch (logoutError) {
      setError(extractErrorMessage(logoutError, 'Failed to sign out'))
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload() {
    if (!file) return
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const response = await uploadLeads(file)
      setMessage(response.message)
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setOffset(0)
      await fetchDashboard({ includeManager: false })
    } catch (uploadError) {
      setError(extractErrorMessage(uploadError, 'Upload failed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleStartCampaign() {
    if (leadStats.pending === 0) {
      setError('No pending leads to start a campaign')
      return
    }
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const response = await startCampaign()
      setMessage(response.message)
      await fetchDashboard({ includeManager: false })
    } catch (startCampaignError) {
      setError(extractErrorMessage(startCampaignError, 'Failed to start campaign'))
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
      await markCallCompleted(lead.call_id)
      setMessage(`Call for ${lead.name} marked as completed`)
      await fetchDashboard({ includeManager: false })
    } catch (markError) {
      setError(extractErrorMessage(markError, 'Failed to mark call completed'))
    }
  }

  async function handleMarkDoNotContact(lead) {
    const reason = window.prompt(`Reason for marking ${lead.name} as do not contact?`, 'requested opt out')
    if (reason === null) return
    try {
      await markLeadDoNotContact(lead.id, reason || 'manual_dnc')
      setMessage(`${lead.name} marked as do not contact`)
      await fetchDashboard({ includeManager: false })
    } catch (markError) {
      setError(extractErrorMessage(markError, 'Failed to mark do not contact'))
    }
  }

  async function handleDeleteLead(lead) {
    const confirmed = window.confirm(
      `Delete ${lead.name} (${lead.phone})? This removes the row so the number can be uploaded again.`,
    )
    if (!confirmed) return

    try {
      const response = await deleteLead(lead.id)
      setMessage(response.message || `${lead.name} deleted`)
      setError('')

      const nextOffset = leadsPayload.items.length === 1 && offset > 0
        ? Math.max(0, offset - leadsPayload.limit)
        : offset
      if (nextOffset !== offset) {
        setOffset(nextOffset)
        return
      }
      await fetchDashboard({ includeManager: false })
    } catch (deleteError) {
      setError(extractErrorMessage(deleteError, 'Failed to delete lead'))
    }
  }

  useEffect(() => {
    loadInitialData()
  }, [loadInitialData])

  useEffect(() => {
    if (initialLoading || (authRequired && !authenticated)) return

    fetchDashboard({ includeManager: false }).catch((fetchError) => {
      if (fetchError?.response?.status === 401) {
        setAuthRequired(true)
        setAuthenticated(false)
        return
      }
      setBackendReachable(false)
      setError(extractErrorMessage(fetchError, 'Failed to refresh leads'))
    })
  }, [authRequired, authenticated, fetchDashboard, initialLoading])

  useEffect(() => {
    if (!authenticated && authRequired) return undefined

    const pollInterval = hasActiveCampaign ? 2000 : 10000
    const interval = setInterval(() => {
      if (document.hidden) return

      pollTickRef.current += 1
      const includeManager = pollTickRef.current % 5 === 0
      fetchDashboard({ includeManager }).catch((pollError) => {
        if (pollError?.response?.status === 401) {
          setAuthRequired(true)
          setAuthenticated(false)
          setBackendReachable(true)
          return
        }
        setBackendReachable(false)
      })
    }, pollInterval)

    return () => clearInterval(interval)
  }, [authRequired, authenticated, fetchDashboard, hasActiveCampaign])

  useEffect(() => {
    setOffset(0)
  }, [search, statusFilter, activeOnly])

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
            <h1>AI Outbound Calling Agent</h1>
            <p className="muted">Upload leads, start campaign, monitor statuses live.</p>
          </div>
          <div className="header-actions">
            {managerStatus && (
              <section className="card manager-card" aria-label="Manager WhatsApp status">
                <MessageCircle size={18} aria-hidden="true" />
                <div>
                  <div><strong>WhatsApp:</strong> {managerStatus.connected ? 'Configured' : 'Not configured'}</div>
                  <div className="muted">Join code: {managerStatus.join_code || '-'}</div>
                </div>
              </section>
            )}
            {authRequired && authenticated ? (
              <button className="secondary" onClick={handleLogout} disabled={loading}>Sign out</button>
            ) : null}
          </div>
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

        {authRequired && !authenticated ? (
          <DashboardLogin
            password={password}
            onPasswordChange={setPassword}
            onSubmit={handleLogin}
            loading={loading}
            error={loginError}
          />
        ) : (
          <>
            <CampaignControls
              file={file}
              loading={loading}
              hasActiveCampaign={hasActiveCampaign}
              pendingCount={leadStats.pending}
              fileInputRef={fileInputRef}
              onFileChange={(event) => setFile(event.target.files?.[0] || null)}
              onUpload={handleUpload}
              onStartCampaign={handleStartCampaign}
            />

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

            <LeadFilters
              search={search}
              status={statusFilter}
              activeOnly={activeOnly}
              onSearchChange={setSearch}
              onStatusChange={setStatusFilter}
              onActiveOnlyChange={setActiveOnly}
            />

            <LeadTable
              leads={leadsPayload.items}
              enableTestEndpoints={ENABLE_TEST_ENDPOINTS}
              onMarkCallCompleted={handleMarkCallCompleted}
              onMarkDoNotContact={handleMarkDoNotContact}
              onDeleteLead={handleDeleteLead}
            />

            <Pagination
              total={leadsPayload.total}
              limit={leadsPayload.limit}
              offset={leadsPayload.offset}
              onPrevious={() => setOffset((current) => Math.max(0, current - leadsPayload.limit))}
              onNext={() => setOffset((current) => current + leadsPayload.limit)}
            />

            <p className="muted" style={{ textAlign: 'center', marginTop: 12 }}>
              Showing {leadsPayload.items.length} of {leadsPayload.total} leads — Auto-refreshing {hasActiveCampaign ? 'every 2s' : 'every 10s'}
            </p>
          </>
        )}
      </main>
    </div>
  )
}
