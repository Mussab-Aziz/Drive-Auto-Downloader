export default function DestCard({ value, onChange, onBrowse, disabled }) {
  return (
    <div className="card">
      <div className="card-title">
        <span className="icon">💾</span>
        Destination
      </div>

      <div className="field">
        <label className="field-label" htmlFor="dest-input">
          Save Location
        </label>
        <div className="input-row">
          <input
            id="dest-input"
            className="input"
            type="text"
            placeholder="C:\Users\YourName\Downloads"
            value={value}
            onChange={e => onChange(e.target.value)}
            spellCheck={false}
            disabled={disabled}
          />
          <button
            id="browse-dest-btn"
            className="btn btn-ghost"
            onClick={onBrowse}
            disabled={disabled}
            title="Open folder picker"
          >
            📁 Browse
          </button>
        </div>
      </div>
    </div>
  )
}
