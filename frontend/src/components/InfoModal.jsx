import { useEffect } from 'react'

export default function InfoModal({ onClose }) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const steps = [
    {
      num: '1',
      title: 'Create a Google Cloud Project',
      color: '#3b82f6',
      items: [
        <>Go to <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" style={linkStyle}>console.cloud.google.com</a></>,
        'Click the project dropdown at the top → "NEW PROJECT"',
        'Enter any name (e.g. "Drive Downloader") and click CREATE',
      ],
    },
    {
      num: '2',
      title: 'Enable Google Drive API',
      color: '#8b5cf6',
      items: [
        'In the Cloud Console, make sure your new project is selected',
        'Go to APIs & Services → Library',
        'Search "Google Drive API" → click it → click ENABLE',
      ],
    },
    {
      num: '3',
      title: 'Create OAuth Credentials (Client Secret)',
      color: '#06b6d4',
      items: [
        'Go to APIs & Services → Credentials',
        'Click "+ CREATE CREDENTIALS" → choose "OAuth client ID"',
        'If prompted, set up the consent screen: choose External → fill in App name & email → Save',
        'Back in Credentials: Application type → Desktop app → CREATE',
        'Click "DOWNLOAD JSON" — this is your Client Secret file ✓',
      ],
    },
    {
      num: '4',
      title: 'First-time Authentication',
      color: '#22c55e',
      items: [
        'Browse to your downloaded client_secret.json in the Client Secret field',
        'Click "Start Download" — a browser window will open',
        'Sign in with your Google account and click Allow',
        'The app saves your session automatically — you only do this once!',
      ],
    },
  ]

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(6px)',
          zIndex: 200,
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Modal */}
      <div style={{
        position: 'fixed',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 201,
        width: 'min(660px, 94vw)',
        maxHeight: '88vh',
        overflowY: 'auto',
        background: '#0e1420',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 20,
        boxShadow: '0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(59,130,246,0.1)',
        animation: 'slideUp 0.25s ease',
      }}>

        {/* Header */}
        <div style={{
          padding: '28px 28px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          position: 'sticky', top: 0,
          background: '#0e1420',
          zIndex: 1,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, flexShrink: 0,
                boxShadow: '0 4px 16px rgba(59,130,246,0.3)',
              }}>🔐</div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                Setting Up Google Credentials
              </h2>
            </div>
            <p style={{ fontSize: 13, color: '#64748b', margin: 0, lineHeight: 1.5 }}>
              One-time setup · Takes about 5 minutes · Free
            </p>
          </div>

          <button
            id="close-info-modal-btn"
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8,
              color: '#94a3b8',
              width: 32, height: 32,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', fontSize: 18, flexShrink: 0,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = '#f1f5f9' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#94a3b8' }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '24px 28px' }}>

          {/* Intro callout */}
          <div style={{
            background: 'rgba(59,130,246,0.08)',
            border: '1px solid rgba(59,130,246,0.2)',
            borderRadius: 10,
            padding: '12px 16px',
            marginBottom: 24,
            fontSize: 13,
            color: '#93c5fd',
            lineHeight: 1.6,
            display: 'flex',
            gap: 10,
          }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>🛡️</span>
            <span>
              Your credentials stay <strong>100% on your computer</strong> — nothing is sent to any server. The app only requests <strong>read-only</strong> access to your Google Drive.
            </span>
          </div>

          {/* Steps */}
          {steps.map((step, idx) => (
            <div key={idx} style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
              {/* Step number */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%',
                  background: `${step.color}22`,
                  border: `2px solid ${step.color}55`,
                  color: step.color,
                  fontWeight: 700, fontSize: 13,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {step.num}
                </div>
                {idx < steps.length - 1 && (
                  <div style={{ width: 2, flex: 1, marginTop: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 1, minHeight: 20 }} />
                )}
              </div>

              {/* Step content */}
              <div style={{ paddingTop: 5, paddingBottom: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 10 }}>
                  {step.title}
                </div>
                <ol style={{ margin: 0, paddingLeft: 18 }}>
                  {step.items.map((item, i) => (
                    <li key={i} style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6, lineHeight: 1.6 }}>
                      {item}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          ))}

          {/* Switch button explanation */}
          <div style={{
            background: 'rgba(139,92,246,0.07)',
            border: '1px solid rgba(139,92,246,0.2)',
            borderRadius: 12,
            padding: '16px 18px',
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{
                background: 'rgba(139,92,246,0.18)',
                border: '1px solid rgba(139,92,246,0.35)',
                color: '#a78bfa',
                fontSize: 12, fontWeight: 600,
                padding: '3px 10px', borderRadius: 6,
              }}>🔄 Switch Account</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>What does this button do?</span>
            </div>
            <p style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 10px', lineHeight: 1.6 }}>
              The <strong style={{ color: '#c4b5fd' }}>Switch</strong> button lets you download from a <strong style={{ color: '#e2e8f0' }}>different Google account</strong> than the one currently logged in.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                { icon: '🗑️', text: 'Deletes your saved token.json (your current login session)' },
                { icon: '🌐', text: 'Next time you start a download, a browser window opens for you to sign in again' },
                { icon: '✅', text: 'Your new account\'s session is then saved for future downloads' },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 13, color: '#94a3b8', alignItems: 'flex-start' }}>
                  <span style={{ flexShrink: 0 }}>{item.icon}</span>
                  <span style={{ lineHeight: 1.5 }}>{item.text}</span>
                </div>
              ))}
            </div>
            <div style={{
              marginTop: 12,
              padding: '8px 12px',
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: 8,
              fontSize: 12,
              color: '#fca5a5',
              display: 'flex', gap: 8, alignItems: 'flex-start',
            }}>
              <span style={{ flexShrink: 0 }}>⚠️</span>
              <span>Only use this if you want to switch Google accounts. Your current session will be logged out.</span>
            </div>
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 0 20px' }} />

          {/* Quick reference */}
          <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Quick Reference
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10 }}>
            {[
              { label: 'Client Secret File', desc: 'The JSON file downloaded from Google Cloud Console', icon: '📄', color: '#06b6d4' },
            ].map((item, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: 10, padding: '12px 14px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 16 }}>{item.icon}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: item.color }}>{item.label}</span>
                </div>
                <p style={{ fontSize: 12, color: '#64748b', margin: 0, lineHeight: 1.5 }}>{item.desc}</p>
              </div>
            ))}
          </div>

          {/* External link */}
          <div style={{ marginTop: 20, textAlign: 'center' }}>
            <a
              href="https://console.cloud.google.com/"
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                fontSize: 13, color: '#3b82f6', textDecoration: 'none',
                fontWeight: 500,
                transition: 'color 0.15s ease',
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#60a5fa'}
              onMouseLeave={e => e.currentTarget.style.color = '#3b82f6'}
            >
              Open Google Cloud Console ↗
            </a>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn  { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideUp { from { opacity: 0; transform: translate(-50%, calc(-50% + 20px)) } to { opacity: 1; transform: translate(-50%, -50%) } }
      `}</style>
    </>
  )
}

const linkStyle = {
  color: '#60a5fa',
  textDecoration: 'none',
  fontWeight: 500,
}
