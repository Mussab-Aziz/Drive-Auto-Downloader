import { useState } from 'react'
import InfoModal from './InfoModal'

export default function AuthCard({
  secretFile, onSecretChange, onBrowseSecret,
  onSwitchAccount,
  disabled,
}) {
  const [showInfo, setShowInfo] = useState(false)

  return (
    <>
      <div className="card">
        <div className="card-title">
          <span className="icon">🔐</span>
          Authentication

          {/* ⓘ Info button */}
          <button
            id="auth-info-btn"
            onClick={() => setShowInfo(true)}
            title="How to get your credentials"
            style={{
              marginLeft: 'auto',
              width: 26,
              height: 26,
              borderRadius: '50%',
              border: '1.5px solid rgba(59,130,246,0.4)',
              background: 'rgba(59,130,246,0.1)',
              color: '#60a5fa',
              fontSize: 13,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
              fontFamily: 'Georgia, serif',
              flexShrink: 0,
              lineHeight: 1,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(59,130,246,0.25)'
              e.currentTarget.style.borderColor = 'rgba(59,130,246,0.7)'
              e.currentTarget.style.transform = 'scale(1.1)'
              e.currentTarget.style.boxShadow = '0 0 12px rgba(59,130,246,0.3)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(59,130,246,0.1)'
              e.currentTarget.style.borderColor = 'rgba(59,130,246,0.4)'
              e.currentTarget.style.transform = 'scale(1)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            i
          </button>
        </div>

        {/* Client Secret File */}
        <div className="field">
          <label className="field-label" htmlFor="secret-input">
            Client Secret File
          </label>
          <div className="input-row">
            <input
              id="secret-input"
              className="input"
              type="text"
              placeholder="path/to/client_secret.json"
              value={secretFile}
              onChange={e => onSecretChange(e.target.value)}
              spellCheck={false}
              disabled={disabled}
            />
            <button
              id="browse-secret-btn"
              className="btn btn-ghost"
              onClick={onBrowseSecret}
              disabled={disabled}
            >
              📄 Browse
            </button>
            <button
              id="switch-account-btn"
              className="btn btn-switch"
              onClick={onSwitchAccount}
              disabled={disabled}
              title="Delete token to re-authenticate with a different Google account"
            >
              🔄 Switch Account
            </button>
          </div>
        </div>

        <div className="tip">
          <span className="tip-icon">💡</span>
          <span>
            Not sure what these files are?{' '}
            <button
              onClick={() => setShowInfo(true)}
              style={{
                background: 'none', border: 'none', padding: 0,
                color: '#60a5fa', cursor: 'pointer', fontSize: 'inherit',
                fontWeight: 600, textDecoration: 'underline', textUnderlineOffset: 3,
              }}
            >
              Click here for a setup guide ↗
            </button>
          </span>
        </div>
      </div>

      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}
    </>
  )
}
