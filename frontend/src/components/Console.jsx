import { useRef, useEffect } from 'react'

export default function Console({ logs, onClear }) {
  const boxRef = useRef(null)

  // Auto-scroll on new logs
  useEffect(() => {
    if (boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight
    }
  }, [logs])

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

      <div className="console-box" ref={boxRef}>
        {logs.length === 0 ? (
          <span className="log-empty">Waiting for download to start...</span>
        ) : (
          logs.map((line, i) => (
            <span key={i} className={`log-line ${line.type}`}>
              {line.text || '\u00a0'}
            </span>
          ))
        )}
      </div>
    </div>
  )
}
