import Header from './components/Header'
import SourceCard from './components/SourceCard'
import DestCard from './components/DestCard'
import AuthCard from './components/AuthCard'
import FiltersCard from './components/FiltersCard'
import Console from './components/Console'
import ActionBar from './components/ActionBar'
import { useDownload } from './hooks/useDownload'

export default function App() {
  const {
    config,
    updateField,
    logs,
    clearLogs,
    isDownloading,
    status,
    startDownload,
    cancelDownload,
    switchAccount,
    browseFolder,
    browseFile,
  } = useDownload()

  return (
    <div className="app-outer">
      <div className="app-grid">

        {/* ── LEFT PANEL: form cards ─────────────────── */}
        <div className="left-panel">
          <Header />

          <SourceCard
            value={config.source_folder_id}
            onChange={v => updateField('source_folder_id', v)}
          />

          <DestCard
            value={config.destination_folder}
            onChange={v => updateField('destination_folder', v)}
            onBrowse={() => browseFolder('destination_folder', 'Select Destination Folder')}
            disabled={isDownloading}
          />

          <AuthCard
            secretFile={config.secret_file}
            onSecretChange={v => updateField('secret_file', v)}
            onBrowseSecret={() => browseFile('secret_file', 'Select Client Secret File')}
            onSwitchAccount={switchAccount}
            disabled={isDownloading}
          />

          <FiltersCard
            skipPhotos={config.skip_photos}
            skipVideos={config.skip_videos}
            skipAudio={config.skip_audio}
            onChange={updateField}
            disabled={isDownloading}
          />
        </div>

        {/* ── RIGHT PANEL: sticky console ────────────── */}
        <div className="right-panel">
          <div className="right-panel-inner">
            <Console logs={logs} onClear={clearLogs} />

            {/* Inline action buttons inside right panel */}
            <div className="inline-action-bar">
              <div className={`status-badge ${status === 'running' ? 'running' : status === 'done' ? 'done' : 'idle'}`}>
                <div className={`status-dot${status === 'running' ? ' pulse' : ''}`} />
                {status === 'running' ? 'Running' : status === 'done' ? 'Done' : 'Idle'}
              </div>

              <button
                id="start-download-btn"
                className={`btn btn-primary${isDownloading ? ' downloading' : ''}`}
                onClick={startDownload}
                disabled={isDownloading}
                style={{ flex: 1 }}
              >
                {isDownloading ? '⏳ Downloading...' : status === 'done' ? '✓ Download Again' : '▶ Start Download'}
              </button>

              <button
                id="cancel-download-btn"
                className="btn btn-danger"
                onClick={cancelDownload}
                disabled={!isDownloading}
                style={{ flexShrink: 0 }}
              >
                ⏹
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
