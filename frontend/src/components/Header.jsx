export default function Header() {
  return (
    <header style={{ padding: '28px 0 20px' }}>
      <h1 style={{
        fontSize: 24,
        fontWeight: 800,
        letterSpacing: '-0.02em',
        background: 'linear-gradient(135deg, #f1f5f9 30%, #94a3b8 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
        marginBottom: 8,
        lineHeight: 1.2,
      }}>
        Drive Auto Downloader
      </h1>

      <p style={{
        fontSize: 14,
        color: 'var(--text-secondary)',
        maxWidth: 420,
        lineHeight: 1.6,
      }}>
        Download entire Google Drive folders automatically while preserving your folder structure.
      </p>

      {/* Subtle divider */}
      <div style={{
        height: 1,
        background: 'linear-gradient(90deg, rgba(59,130,246,0.4) 0%, rgba(139,92,246,0.2) 50%, transparent 100%)',
        marginTop: 28,
      }} />
    </header>
  )
}
