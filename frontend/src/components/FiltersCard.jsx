function Toggle({ id, label, emoji, checked, onChange, disabled }) {
  return (
    <label
      htmlFor={id}
      className={`toggle-label${checked ? ' active' : ''}`}
      style={{ opacity: disabled ? 0.5 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
    >
      <span>{emoji}</span>
      <div className={`toggle-track${checked ? ' on' : ''}`}>
        <div className="toggle-thumb" />
      </div>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={e => !disabled && onChange(e.target.checked)}
        style={{ display: 'none' }}
      />
      {label}
    </label>
  )
}

export default function FiltersCard({
  skipPhotos, skipVideos, skipAudio, skipGoogleFiles,
  maxWorkers, onChange, disabled,
}) {
  return (
    <div className="card">
      <div className="card-title">
        <span className="icon">🎯</span>
        File Filters
        <span style={{
          fontSize: 10,
          fontWeight: 500,
          color: 'var(--text-muted)',
          textTransform: 'none',
          letterSpacing: 0,
          marginLeft: 4,
        }}>
          optional
        </span>
      </div>

      <div className="toggles-row">
        <Toggle
          id="toggle-photos"
          label="Skip Photos"
          emoji="🖼️"
          checked={skipPhotos}
          onChange={v => onChange('skip_photos', v)}
          disabled={disabled}
        />
        <Toggle
          id="toggle-videos"
          label="Skip Videos"
          emoji="🎬"
          checked={skipVideos}
          onChange={v => onChange('skip_videos', v)}
          disabled={disabled}
        />
        <Toggle
          id="toggle-audio"
          label="Skip Audio"
          emoji="🎵"
          checked={skipAudio}
          onChange={v => onChange('skip_audio', v)}
          disabled={disabled}
        />
        <Toggle
          id="toggle-skip-google"
          label="Skip Workspace"
          emoji="📝"
          checked={skipGoogleFiles}
          onChange={v => onChange('skip_google_files', v)}
          disabled={disabled}
        />
      </div>

      {/* ── Parallel connections slider ────────────────────────────── */}
      <div className="parallel-row">
        <div className="parallel-label">
          <span>⚡ Parallel Connections</span>
          <span className="parallel-badge">{maxWorkers}</span>
        </div>
        <input
          id="parallel-slider"
          type="range"
          min={1}
          max={8}
          step={1}
          value={maxWorkers}
          disabled={disabled}
          onChange={e => onChange('max_workers', Number(e.target.value))}
          className="parallel-slider"
          style={{ opacity: disabled ? 0.5 : 1 }}
        />
        <div className="parallel-hints">
          <span>1 (safe)</span>
          <span>4 (recommended)</span>
          <span>8 (max)</span>
        </div>
      </div>
    </div>
  )
}
