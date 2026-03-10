export default function LeadFilters({
  search,
  status,
  activeOnly,
  onSearchChange,
  onStatusChange,
  onActiveOnlyChange,
}) {
  return (
    <section className="card filter-card" aria-label="Lead filters">
      <div className="filter-grid">
        <div>
          <label htmlFor="lead-search">Search</label>
          <input
            id="lead-search"
            type="search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Name, phone, or location"
          />
        </div>
        <div>
          <label htmlFor="lead-status">Status</label>
          <select id="lead-status" value={status} onChange={(event) => onStatusChange(event.target.value)}>
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="queued">Queued</option>
            <option value="calling">Calling</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="voicemail">Voicemail</option>
            <option value="dnc">DNC</option>
          </select>
        </div>
        <label className="checkbox-row" htmlFor="active-only">
          <input
            id="active-only"
            type="checkbox"
            checked={activeOnly}
            onChange={(event) => onActiveOnlyChange(event.target.checked)}
          />
          Active leads only
        </label>
      </div>
    </section>
  )
}
