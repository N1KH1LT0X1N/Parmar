export default function DashboardLogin({ password, onPasswordChange, onSubmit, loading, error }) {
  return (
    <section className="card auth-card" aria-label="Dashboard login">
      <h2>Dashboard login required</h2>
      <p className="muted">Enter the dashboard password configured on the backend.</p>
      <form className="auth-form" onSubmit={onSubmit}>
        <label htmlFor="dashboard-password">Password</label>
        <input
          id="dashboard-password"
          type="password"
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
          autoComplete="current-password"
        />
        <button className="primary" type="submit" disabled={!password || loading}>
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
      {error ? <p className="error" role="alert">{error}</p> : null}
    </section>
  )
}
