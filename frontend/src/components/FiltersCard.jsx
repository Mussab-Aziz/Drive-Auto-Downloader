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

export default function FiltersCard({ skipPhotos, skipVideos, skipAudio, onChange, disabled }) {
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
      </div>
    </div>
  )
}
