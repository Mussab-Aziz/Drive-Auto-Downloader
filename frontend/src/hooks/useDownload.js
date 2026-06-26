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
  })
  const [logs, setLogs] = useState([])
  const [isDownloading, setIsDownloading] = useState(false)
  const [status, setStatus] = useState('idle') // 'idle' | 'running' | 'done'
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
    const res = await fetch('/api/browse/folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
    const data = await res.json()
    if (data.path) updateField(field, data.path)
  }, [updateField])

  // Browse file
  const browseFile = useCallback(async (field, title) => {
    const res = await fetch('/api/browse/file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
    const data = await res.json()
    if (data.path) updateField(field, data.path)
  }, [updateField])

  // Classify log line for styling
  function classifyLine(line) {
    const l = line.toLowerCase()
    if (l.includes('[success]') || l.includes('✓') || l.includes('completed')) return 'success'
    if (l.includes('[error]') || l.includes('❌') || l.includes('failed')) return 'error'
    if (l.includes('[!]') || l.includes('warning')) return 'warning'
    if (l.includes('[info]') || l.includes('starting') || l.includes('building') || l.includes('verifying') || l.includes('scanning')) return 'info'
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
        setIsDownloading(false)
        setStatus('done')
        es.close()
        esRef.current = null
        return
      }
      const text = raw.replace(/\\n/g, '\n')
      const lines = text.split('\n')
      setLogs(prev => [
        ...prev,
        ...lines.map(line => ({ text: line, type: classifyLine(line) }))
      ])
    }

    es.onerror = () => {
      setIsDownloading(false)
      setStatus('idle')
      es.close()
      esRef.current = null
    }
  }

  const startDownload = useCallback(async () => {
    if (isDownloading) return
    setLogs([])
    setStatus('running')
    setIsDownloading(true)

    const res = await fetch('/api/download/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    const data = await res.json()

    if (!data.ok) {
      setLogs([{ text: `[ERROR] ${data.error}`, type: 'error' }])
      setIsDownloading(false)
      setStatus('idle')
      return
    }

    startLogStream()
  }, [config, isDownloading])

  const cancelDownload = useCallback(async () => {
    await fetch('/api/download/cancel', { method: 'POST' })
  }, [])

  const clearLogs = useCallback(() => setLogs([]), [])

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
      setLogs(prev => [...prev, { text: `[ERROR] ${data.error}`, type: 'error' }])
    }
  }, [config.token_file])

  return {
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
  }
}
