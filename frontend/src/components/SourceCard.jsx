export default function SourceCard({ value, onChange }) {
  return (
    <div className="card">
      <div className="card-title">
        <span className="icon">📤</span>
        Source
      </div>

      <div className="field">
        <label className="field-label" htmlFor="source-input">
          Google Drive Folder Link or ID
        </label>
        <input
          id="source-input"
          className="input"
          type="text"
          placeholder="https://drive.google.com/drive/folders/... or folder ID"
          value={value}
          onChange={e => onChange(e.target.value)}
          spellCheck={false}
          autoComplete="off"
        />
      </div>
    </div>
  )
}
