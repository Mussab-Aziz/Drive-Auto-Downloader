export default function ActionBar({ isDownloading, status, onStart, onCancel }) {
  const getStartLabel = () => {
    if (isDownloading) return '⏳ Downloading...'
    if (status === 'done') return '✓ Download Again'
    return '▶ Start Download'
  }

  return (
    <div className="action-bar">
      <div className="action-bar-inner">
        {/* Status badge */}
        <div className={`status-badge ${status === 'running' ? 'running' : status === 'done' ? 'done' : 'idle'}`}>
          <div className={`status-dot${status === 'running' ? ' pulse' : ''}`} />
          {status === 'running' ? 'Running' : status === 'done' ? 'Done' : 'Idle'}
        </div>

        {/* Start button */}
        <button
          id="start-download-btn"
          className={`btn btn-primary${isDownloading ? ' downloading' : ''}`}
          onClick={onStart}
          disabled={isDownloading}
        >
          {getStartLabel()}
        </button>

        {/* Cancel button */}
        <button
          id="cancel-download-btn"
          className="btn btn-danger"
          onClick={onCancel}
          disabled={!isDownloading}
        >
          ⏹ Cancel
        </button>
      </div>
    </div>
  )
}
