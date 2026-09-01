import { useRef, useEffect } from 'react'

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatSpeed(mbps) {
  if (!mbps || mbps === 0) return ''
  if (mbps >= 1) return `${mbps.toFixed(1)} MB/s`
  return `${(mbps * 1024).toFixed(0)} KB/s`
}

function formatEta(sec) {
  if (!sec || sec <= 0) return ''
  if (sec < 60) return `ETA ${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `ETA ${m}m ${s}s`
}

function formatSize(mb) {
  if (!mb) return ''
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${mb} MB`
}

// ── Combined speed banner (parallel mode) ────────────────────────────────────

function CombinedSpeedBar({ totalSpeedMbps, activeCount }) {
  const speed = formatSpeed(totalSpeedMbps)
  return (
    <div className="combined-speed-wrap">
      <div className="combined-speed-left">
        <span className="combined-speed-dot" />
        <span className="combined-speed-label">
          {activeCount} file{activeCount !== 1 ? 's' : ''} downloading in parallel
        </span>
      </div>
      <div className="combined-speed-right">
        {speed
          ? <span className="combined-speed-value">⚡ {speed} combined</span>
          : <span className="combined-speed-value dim">⚡ Starting…</span>
        }
      </div>
    </div>
  )
}

// ── Active Live Download Progress Bar ────────────────────────────────────────

function ActiveProgressBar({ percent, speedMbps, etaSec, sizeMb }) {
  const speed = formatSpeed(speedMbps)
  const eta   = formatEta(etaSec)
  const size  = formatSize(sizeMb)

  return (
    <div className="active-progress-wrap">
      {/* Top row: Status & Percentage */}
      <div className="active-progress-top">
        <div className="active-progress-status">
          <span className="active-progress-dot" />
          <span>Downloading...</span>
        </div>
        <span className="active-progress-pct">{percent}%</span>
      </div>

      {/* Middle row: Progress track */}
      <div className="active-progress-track">
        <div
          className="active-progress-fill"
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Bottom row: Speed on left, ETA & Total Size on right */}
      <div className="active-progress-footer">
        <div className="active-footer-left">
          {speed ? (
            <span className="active-meta-speed">⚡ {speed}</span>
          ) : (
            <span className="active-meta-speed dim">⚡ Starting...</span>
          )}
        </div>
        <div className="active-footer-right">
          {eta && <span className="active-meta-eta">⏱ {eta}</span>}
          {size && <span className="active-meta-size">📦 {size}</span>}
        </div>
      </div>
    </div>
  )
}

// ── Overall file counter bar ──────────────────────────────────────────────────

function OverallProgress({ current, total }) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0
  return (
    <div className="overall-progress-wrap">
      <div className="overall-progress-header">
        <span className="overall-progress-label">📦 File {current} of {total}</span>
        <span className="overall-progress-pct">{pct}%</span>
      </div>
      <div className="overall-progress-track">
        <div className="overall-progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// ── Console component ─────────────────────────────────────────────────────────

export default function Console({ logs, onClear, overallProgress, activeProgress, combinedSpeed }) {
  const boxRef = useRef(null)

  useEffect(() => {
    if (boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight
    }
  }, [logs, activeProgress, combinedSpeed])

  // In parallel mode show the combined banner instead of the single-file bar
  const isParallel = combinedSpeed && combinedSpeed.activeCount > 1

  return (
    <div className="card console-wrap" style={{ flex: 1, minHeight: 0, marginBottom: 0 }}>
      <div className="console-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="console-dots">
            <div className="console-dot red" />
            <div className="console-dot yellow" />
            <div className="console-dot green" />
          </div>
          <span className="console-title">Console Output</span>
        </div>
        <button
          id="clear-console-btn"
          className="btn btn-ghost"
          onClick={onClear}
          style={{ padding: '4px 12px', fontSize: 11 }}
        >
          Clear
        </button>
      </div>

      {/* Overall progress bar sits above the log box */}
      {overallProgress && (
        <OverallProgress
          current={overallProgress.current}
          total={overallProgress.total}
        />
      )}

      <div className="console-box" ref={boxRef}>
        {logs.length === 0 && !activeProgress && !combinedSpeed ? (
          <span className="log-empty">Waiting for download to start...</span>
        ) : (
          <>
            {logs.map((line, i) => (
              <span key={i} className={`log-line ${line.type}`}>
                {line.text || '\u00a0'}
              </span>
            ))}

            {/* Parallel mode: combined throughput banner */}
            {isParallel && (
              <CombinedSpeedBar
                totalSpeedMbps={combinedSpeed.totalSpeedMbps}
                activeCount={combinedSpeed.activeCount}
              />
            )}

            {/* Single-file mode: individual progress bar */}
            {!isParallel && activeProgress && (
              <ActiveProgressBar
                percent={activeProgress.percent}
                speedMbps={activeProgress.speedMbps}
                etaSec={activeProgress.etaSec}
                sizeMb={activeProgress.sizeMb}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
