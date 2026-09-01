import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useDownload – central state + SSE log streaming hook
 */
export function useDownload() {
  const [config, setConfig] = useState({
    source_folder_id: '',
    destination_folder: '',
    secret_file: '',
    skip_photos: false,
    skip_videos: false,
    skip_audio: false,
    skip_google_files: false,
  })
  const [logs, setLogs] = useState([])
  const [activeProgress, setActiveProgress] = useState(null) // {percent, speedMbps, etaSec, sizeMb} | null
  const [isDownloading, setIsDownloading] = useState(false)
  const [status, setStatus] = useState('idle') // 'idle' | 'running' | 'done'
  const [overallProgress, setOverallProgress] = useState(null) // {current, total} | null
  const esRef = useRef(null)

  // Load config on mount
  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(data => setConfig(prev => ({ ...prev, ...data })))
      .catch(() => {})
  }, [])

  // Helper to save config automatically
  const saveConfig = useCallback((updatedConfig) => {
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedConfig),
    }).catch(() => {})
  }, [])

  const updateField = useCallback((field, value) => {
    setConfig(prev => {
      const updated = { ...prev, [field]: value }
      saveConfig(updated)
      return updated
    })
  }, [saveConfig])

  // Browse folder
  const browseFolder = useCallback(async (field, title) => {
    try {
      const res = await fetch('/api/browse/folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const data = await res.json()
      if (data.path) updateField(field, data.path)
    } catch (err) {
      setLogs(prev => [...prev, { text: `[ERROR] Browse failed: ${err.message ?? err}`, type: 'error' }])
    }
  }, [updateField])

  // Browse file
  const browseFile = useCallback(async (field, title) => {
    try {
      const res = await fetch('/api/browse/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const data = await res.json()
      if (data.path) updateField(field, data.path)
    } catch (err) {
      setLogs(prev => [...prev, { text: `[ERROR] Browse failed: ${err.message ?? err}`, type: 'error' }])
    }
  }, [updateField])

  // Classify log line for styling
  function classifyLine(line) {
    const l = line.toLowerCase()
    if (l.includes('successfully') || l.includes('✓') || l.includes('[success]') || l.includes('completed')) return 'success'
    if (l.includes('[error]') || l.includes('❌') || l.includes('failed')) return 'error'
    if (l.includes('[!]') || l.includes('warning')) return 'warning'
    if (l.includes('[info]') || l.includes('starting') || l.includes('building') || l.includes('verifying') || l.includes('scanning') || l.includes('downloading:')) return 'info'
    if (l.includes('skipping')) return 'dim'
    return 'default'
  }

  // Start SSE stream
  function startLogStream() {
    if (esRef.current) esRef.current.close()
    const es = new EventSource('/api/download/logs')
    esRef.current = es

    es.onmessage = (e) => {
      const raw = e.data
      if (raw === '__PING__') return
      if (raw === '__DONE__') {
        setActiveProgress(null)
        setIsDownloading(false)
        setStatus('done')
        setOverallProgress(null)
        es.close()
        esRef.current = null
        return
      }

      // Try to parse as structured JSON (progress, overall_progress, etc.)
      try {
        const parsed = JSON.parse(raw)

        // Per-file live progress
        if (parsed.type === 'progress') {
          setActiveProgress({
            percent: parsed.percent,
            speedMbps: parsed.speed_mbps ?? 0,
            etaSec: parsed.eta_sec ?? null,
            sizeMb: parsed.size_mb ?? null,
          })
          return
        }

        // Overall file counter
        if (parsed.type === 'overall_progress') {
          setOverallProgress({ current: parsed.current, total: parsed.total })
          return
        }

        // It was valid JSON but of another type — don't dump raw JSON to console logs
        return
      } catch (_) {
        // Not JSON — fall through to plain-text handling
      }

      const text = raw.replace(/\\n/g, '\n')
      const lines = text.split('\n')

      for (const line of lines) {
        const lower = line.toLowerCase()
        if (lower.includes('downloading:')) {
          // Instant 0ms progress bar initialization
          setActiveProgress(prev => ({
            percent: 0,
            speedMbps: 0,
            etaSec: null,
            sizeMb: prev?.sizeMb ?? null,
          }))
        } else if (
          line.includes('✓') ||
          lower.includes('successfully downloaded') ||
          lower.includes('skipping:') ||
          lower.includes('download completed')
        ) {
          // File completed or skipped — remove active progress bar
          setActiveProgress(null)
        }
      }

      setLogs(prev => [
        ...prev,
        ...lines.map(line => ({ text: line, type: classifyLine(line) }))
      ])
    }

    es.onerror = () => {
      setActiveProgress(null)
      setIsDownloading(false)
      setStatus('idle')
      setOverallProgress(null)
      es.close()
      esRef.current = null
    }
  }

  const startDownload = useCallback(async () => {
    if (isDownloading) return
    setLogs([])
    setActiveProgress(null)
    setOverallProgress(null)
    setStatus('running')
    setIsDownloading(true)

    const res = await fetch('/api/download/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    const data = await res.json()

    if (!data.ok) {
      setLogs([{ text: `[ERROR] ${data.error ?? 'Unknown error — check your inputs and try again.'}`, type: 'error' }])
      setIsDownloading(false)
      setStatus('idle')
      return
    }

    startLogStream()
  }, [config, isDownloading])

  const cancelDownload = useCallback(async () => {
    try {
      const res = await fetch('/api/download/cancel', { method: 'POST' })
      const data = await res.json()
      if (data.ok) {
        // Immediately reflect cancellation in the UI
        setActiveProgress(null)
        setIsDownloading(false)
        setStatus('idle')
        setOverallProgress(null)
        setLogs(prev => [
          ...prev,
          { text: '[INFO] Download cancelled by user.', type: 'info' },
        ])
        if (esRef.current) {
          esRef.current.close()
          esRef.current = null
        }
      }
    } catch (e) {
      console.error('Cancel failed:', e)
    }
  }, [])

  const clearLogs = useCallback(() => {
    setLogs([])
    setActiveProgress(null)
  }, [])

  const switchAccount = useCallback(async () => {
    const res = await fetch('/api/account/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    const data = await res.json()
    if (data.ok) {
      setLogs([
        { text: '═'.repeat(60), type: 'info' },
        { text: 'ACCOUNT SWITCHED — FOLLOW THESE STEPS:', type: 'success' },
        { text: '═'.repeat(60), type: 'info' },
        { text: '', type: 'default' },
        { text: '1. Click "Start Download" with any folder ID', type: 'default' },
        { text: '2. A browser window will open asking you to sign in', type: 'default' },
        { text: '3. After authentication, the download will begin', type: 'default' },
        { text: '4. Your new token will be saved for future downloads', type: 'default' },
        { text: '', type: 'default' },
        { text: '═'.repeat(60), type: 'info' },
      ])
    } else {
      setLogs(prev => [...prev, { text: `[ERROR] ${data.error ?? 'Failed to switch account'}`, type: 'error' }])
    }
  }, [config.token_file])

  return {
    config,
    updateField,
    logs,
    activeProgress,
    clearLogs,
    isDownloading,
    status,
    overallProgress,
    startDownload,
    cancelDownload,
    switchAccount,
    browseFolder,
    browseFile,
  }
}
