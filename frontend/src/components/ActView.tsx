import L from 'leaflet'
import { useEffect, useState } from 'react'
import { api, type ParcelDetail } from '../api'
import { formatArea, formatDate, formatDateTime, todayISO } from '../format'
import { useI18n } from '../i18n'

/** Печатная форма «Акт осмотра земельного участка» — сохраняется в PDF средствами браузера. */
export default function ActView({ id }: { id: number }) {
  const i = useI18n()
  const [parcel, setParcel] = useState<ParcelDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.parcel(id).then(setParcel).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    if (!parcel) return
    document.title = `${i.t('actTitle')} ${parcel.cadastral_no}`
  }, [parcel, i])

  if (error) return <div className="act act--error">{error}</div>
  if (!parcel) return <div className="act">…</div>

  const center = L.geoJSON(parcel.geometry).getBounds().getCenter()
  const active = parcel.lifecycle === 'detected' || parcel.lifecycle === 'in_progress'
  const number = `${parcel.cadastral_no.replace(/-/g, '')}-${todayISO().replace(/-/g, '')}`
  const photos = parcel.photos.slice(0, 4)

  return (
    <div className="act">
      <div className="act__toolbar no-print">
        <button className="btn btn--primary" onClick={() => window.print()}>
          🖨 {i.t('actPrint')}
        </button>
      </div>

      <header className="act__head">
        <div className="act__org">
          {i.t('office')}
          <br />
          {i.lang === 'kz' ? 'Жамбыл облысы әкімдігі' : 'Акимат Жамбылской области'}
        </div>
        <h1>
          {i.t('actTitle')} № {number}
        </h1>
        <div className="act__meta">
          <span>
            {i.t('actDate')}: <b>{formatDate(todayISO(), i.lang)}</b>
          </span>
          <span>
            {i.t('actInspector')}: ______________________
          </span>
        </div>
      </header>

      <table className="act__table">
        <tbody>
          <tr>
            <th>{i.t('cadastralNo')}</th>
            <td className="mono">{parcel.cadastral_no}</td>
          </tr>
          <tr>
            <th>{i.t('address')}</th>
            <td>{parcel.address}</td>
          </tr>
          <tr>
            <th>{i.t('purpose')}</th>
            <td>{i.d.purposeName[parcel.purpose]}</td>
          </tr>
          <tr>
            <th>{i.t('area')}</th>
            <td>
              {formatArea(parcel.area_ha)} {i.t('ha')}
            </td>
          </tr>
          <tr>
            <th>{i.t('owner')}</th>
            <td>{parcel.owner || '—'}</td>
          </tr>
          <tr>
            <th>{i.t('actCoords')}</th>
            <td className="mono">
              {center.lat.toFixed(6)}, {center.lng.toFixed(6)}
            </td>
          </tr>
        </tbody>
      </table>

      <h2>{i.t('actFindings')}</h2>
      <p>
        <b>{i.d.lifecycle[parcel.lifecycle]}</b>
        {parcel.violation_type && parcel.lifecycle !== 'none' && <> — {i.d.violation[parcel.violation_type]}</>}
      </p>
      {parcel.signals.length > 0 && (
        <ul className="act__list">
          {parcel.signals.map((s) => (
            <li key={s.id}>
              <span className="mono">{s.code}</span> ({formatDateTime(s.created_at, i.lang)}): {s.description}
            </li>
          ))}
        </ul>
      )}

      {photos.length > 0 && (
        <div className="act__photos">
          {photos.map((p) => (
            <figure key={p.id}>
              <img src={p.url} alt="" />
              <figcaption>
                {p.source === 'citizen' ? i.t('byCitizen') : i.t('byInspector')} · {formatDateTime(p.created_at, i.lang)}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      <h2>{i.t('actPrescription')}</h2>
      <p>
        {active
          ? parcel.deadline && parcel.violation_type
            ? i.t('actPrescriptionText', {
                violation: i.d.violation[parcel.violation_type],
                deadline: formatDate(parcel.deadline, i.lang),
              })
            : i.t('actNoDeadline')
          : i.t('actNoPrescription')}
      </p>

      <div className="act__signs">
        <div>
          {i.t('actInspector')}
          <span className="act__line" />
          <small>{i.t('actSignature')}</small>
        </div>
        <div>
          {i.t('actOwner')}
          <span className="act__line" />
          <small>{i.t('actSignature')}</small>
        </div>
      </div>

      <footer className="act__foot">
        {i.t('actGenerated')} · {formatDateTime(new Date().toISOString(), i.lang)}
      </footer>
    </div>
  )
}
