import { Play, Upload } from 'lucide-react'

export default function CampaignControls({
  file,
  loading,
  hasActiveCampaign,
  pendingCount,
  fileInputRef,
  onFileChange,
  onUpload,
  onStartCampaign,
}) {
  return (
    <section className="card" style={{ marginBottom: 16 }} aria-label="Campaign controls">
      <div className="controls">
        <label htmlFor="lead-upload-input" className="sr-only">Upload Leads CSV</label>
        <input
          id="lead-upload-input"
          ref={fileInputRef}
          aria-label="Upload Leads CSV"
          type="file"
          accept=".csv"
          onChange={onFileChange}
        />
        <button className="secondary" onClick={onUpload} disabled={!file || loading}>
          <Upload size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" /> Upload
        </button>
        <button
          className="primary"
          onClick={onStartCampaign}
          disabled={loading || hasActiveCampaign || pendingCount === 0}
        >
          <Play size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" />
          {hasActiveCampaign ? 'Campaign Running...' : 'Start Campaign'}
        </button>
      </div>
    </section>
  )
}
