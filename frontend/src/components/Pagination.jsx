export default function Pagination({ total, limit, offset, onPrevious, onNext }) {
  if (total <= limit) return null

  const page = Math.floor(offset / limit) + 1
  const pageCount = Math.max(1, Math.ceil(total / limit))

  return (
    <div className="pagination" aria-label="Lead pagination">
      <button className="secondary" onClick={onPrevious} disabled={offset === 0}>Previous</button>
      <span className="muted">Page {page} of {pageCount}</span>
      <button className="secondary" onClick={onNext} disabled={offset + limit >= total}>Next</button>
    </div>
  )
}
