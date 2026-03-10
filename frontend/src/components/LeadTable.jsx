function statusClass(status) {
  return `status-chip status-${status || 'pending'}`
}

function interestClass(level) {
  if (!level) return 'interest-chip interest-unknown'
  return `interest-chip interest-${level}`
}

function canDeleteLead(lead) {
  return ['completed', 'failed', 'voicemail', 'dnc'].includes(lead.status)
}

export default function LeadTable({ leads, enableTestEndpoints, onMarkCallCompleted, onMarkDoNotContact, onDeleteLead }) {
  return (
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
            <th scope="col">Outcome</th>
            <th scope="col">Summary</th>
            <th scope="col" style={{ width: 180 }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {leads.length === 0 ? (
            <tr>
              <td colSpan={8} className="muted">No leads uploaded yet.</td>
            </tr>
          ) : (
            leads.map((lead) => (
              <tr key={lead.id}>
                <td>{lead.name}</td>
                <td className="phone-cell">{lead.phone}</td>
                <td>{lead.location || '-'}</td>
                <td><span className={statusClass(lead.status)}>{lead.status}</span></td>
                <td><span className={interestClass(lead.interest_level)}>{lead.interest_level || '-'}</span></td>
                <td>{lead.contact_outcome || '-'}</td>
                <td className="summary-cell">{lead.summary || '-'}</td>
                <td>
                  <div className="action-stack">
                    {enableTestEndpoints && lead.status === 'calling' && lead.call_id ? (
                      <button
                        className="action-btn"
                        onClick={() => onMarkCallCompleted(lead)}
                        title="Complete the ongoing call (for testing)"
                        aria-label={`End call for ${lead.name}`}
                      >
                        End Call
                      </button>
                    ) : null}
                    {!lead.do_not_contact ? (
                      <button
                        className="secondary action-secondary"
                        onClick={() => onMarkDoNotContact(lead)}
                        aria-label={`Mark ${lead.name} as do not contact`}
                      >
                        Mark DNC
                      </button>
                    ) : null}
                    {canDeleteLead(lead) ? (
                      <button
                        className="danger action-secondary"
                        onClick={() => onDeleteLead(lead)}
                        aria-label={`Delete ${lead.name}`}
                      >
                        Delete
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  )
}
