import { useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const i = useI18n()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  return (
    <div className="login">
      <form
        className="login__card"
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          setError(null)
          try {
            await api.login(password)
            onSuccess()
          } catch (err) {
            setError((err as Error).message)
          } finally {
            setBusy(false)
          }
        }}
      >
        <div className="brand brand--dark">
          <span className="brand__mark" aria-hidden>
            <svg viewBox="0 0 32 32">
              <path d="M6 23 L13 8 L26 12 L21 25 Z" />
              <circle cx="16" cy="16" r="3" />
            </svg>
          </span>
          <span>
            <span className="brand__name">ЖерКөз</span>
            <span className="brand__sub">{i.t('loginHint')}</span>
          </span>
        </div>
        <h1>{i.t('login')}</h1>
        <label className="field">
          <span>{i.t('password')}</span>
          <input type="password" autoFocus autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="text-bad small">{error}</p>}
        <button className="btn btn--primary" disabled={busy || !password}>
          {busy ? i.t('signingIn') : i.t('signIn')}
        </button>
        <div className="lang-switch lang-switch--light" role="group">
          {(['kz', 'ru'] as const).map((l) => (
            <button type="button" key={l} className={i.lang === l ? 'is-active' : ''} onClick={() => i.setLang(l)}>
              {l === 'kz' ? 'ҚАЗ' : 'РУС'}
            </button>
          ))}
        </div>
      </form>
    </div>
  )
}
