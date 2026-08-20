import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { fetchCatalogueStatus, fetchComparisons, fetchDevice, fetchDevices, searchDevices } from './api'
import './styles.css'

const initialFilters = {
  query: '', category: '', brand: '', operating_system: '', use_case: 'Personal',
  price_min: 0, price_max: 3000, cpu_speed: 0, ram: 0, storage: 0,
}

function scoreCopy(level, score) {
  if (level === 'Excellent') return `Strong baseline (${score}%). Good fit for most everyday setups.`
  if (level === 'Good') return `A sensible baseline (${score}%). Review the suggested controls before deployment.`
  if (level === 'Adequate') return `Usable with care (${score}%). Plan updates, encryption and account protection.`
  return `Extra care needed (${score}%). Check the risks before choosing this device.`
}

function DeviceCard({ device, onSelect }) {
  const score = device.security?.score ?? 0
  const level = device.security?.level || 'Unrated'
  return <article className="device-card">
    <div className="device-card-top">
      {device.image && <img className="device-thumb" src={device.image} alt="" loading="lazy" />}
      <div><span className="eyebrow">{device.category}</span><h3>{device.name}</h3></div>
      <span className={`score score-${level.toLowerCase()}`}>{score}%</span>
    </div>
    <p className="muted">{device.os} · {device.ram} GB RAM · {device.storage} GB storage</p>
    <p className="plain-score"><strong>{level} security baseline.</strong> {scoreCopy(level, score)}</p>
    <p className="small-note">Catalogue source: {device.catalogue?.source || 'Curated local catalogue'} · {device.catalogue?.availability || 'availability unknown'}</p>
    <div className="card-footer"><strong>£{Number(device.price).toLocaleString()}</strong><button onClick={() => onSelect(device.id)}>Review device</button></div>
  </article>
}

function Metric({ label, value }) {
  return <span className="metric"><small>{label}</small><strong>{value}</strong></span>
}

function DeviceDetail({ device, comparisons, onCompare, onClose }) {
  const security = device.security || {}
  const benchmark = device.benchmark || {}
  const tools = device.debloat_tools || []
  return <section className="detail-panel">
    <div className="section-heading"><div><span className="eyebrow">03 · Device review</span><h2>{device.name}</h2><p className="lead">{device.os} · {device.cpu_vendor} · {device.category}</p></div><button className="quiet" onClick={onClose}>Close</button></div>
    <div className="metric-row"><Metric label="Security score" value={`${security.score ?? 0}% · ${security.level || 'Unrated'}`} /><Metric label="Price shown" value={`£${device.price}`} /><Metric label="Memory" value={`${device.ram} GB`} /><Metric label="Storage" value={`${device.storage} GB`} /></div>
    <p className="freshness-note">Source: <strong>{device.catalogue?.source || 'Curated local catalogue'}</strong> · Price checked: {device.catalogue?.price_checked_at || 'not supplied'} · Availability: {device.catalogue?.availability || 'unknown'}</p>
    <div className="detail-grid">
      <div className="detail-column">
        <section className="guidance-block"><h3>What this means</h3><p>{scoreCopy(security.level, security.score ?? 0)}</p><p className="small-note">This is a practical comparison aid, not a security certification or a guarantee.</p></section>
        <section className="guidance-block"><h3>Do these things first</h3><ul>{(security.recommendations || []).slice(0, 8).map((item, index) => <li key={index}>{item}</li>)}</ul></section>
        <section className="guidance-block"><h3>Risks to understand</h3>{(security.findings || []).length ? <ul>{security.findings.slice(0, 6).map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No specific risk was flagged by the current rules. Keep the normal update, encryption and account-safety steps.</p>}</section>
      </div>
      <div className="detail-column">
        <section className="comparison-box"><h3>Performance at a glance</h3><div className="benchmark-grid"><Metric label="Overall" value={`${benchmark.overall_index ?? 0}/100`} /><Metric label="CPU" value={`${benchmark.cpu_index ?? 0}/100`} /><Metric label="Memory" value={`${benchmark.memory_index ?? 0}/100`} /><Metric label="Storage" value={`${benchmark.storage_index ?? 0}/100`} /></div><p className="small-note">These are normalized comparisons based on the catalogue data, not laboratory benchmarks.</p></section>
        <section className="comparison-box"><h3>Improve performance</h3>{tools.length ? <div className="tool-list">{tools.slice(0, 4).map((tool, index) => <a key={index} href={tool.url} target="_blank" rel="noreferrer noopener"><strong>{tool.name}</strong><span>{tool.description}</span></a>)}</div> : <p>Keep the operating system updated, remove unused software and leave enough free storage for updates.</p>}</section>
        <section className="comparison-box"><h3>Where to compare prices</h3><p className="small-note">Prices and availability can change. Verify the final details before buying.</p><div className="retailer-list">{Object.entries(device.retailer_links || {}).slice(0, 6).map(([name, url]) => <a key={name} href={url} target="_blank" rel="noreferrer noopener">{name}</a>)}</div></section>
      </div>
    </div>
    <section className="comparison-box alternatives"><div className="section-heading"><div><h3>Similar choices</h3><p className="small-note">Compare nearby options with similar price and performance.</p></div><button className="secondary" onClick={onCompare}>Find alternatives</button></div>{comparisons.length ? <div className="mini-grid">{comparisons.map(item => <div className="mini-card" key={item.id}><strong>{item.name}</strong><span>£{item.price} · {item.security?.score}% security score</span></div>)}</div> : <p className="small-note">Choose “Find alternatives” to load comparisons.</p>}</section>
  </section>
}

function App() {
  const [filters, setFilters] = useState(initialFilters)
  const [sort, setSort] = useState('security')
  const [devices, setDevices] = useState([])
  const [total, setTotal] = useState(0)
  const [catalogueStatus, setCatalogueStatus] = useState(null)
  const [selected, setSelected] = useState(null)
  const [comparisons, setComparisons] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async (values = filters) => {
    setLoading(true); setError('')
    try {
      const payload = values.query ? await searchDevices(values) : await fetchDevices(values)
      setDevices(payload.items || []); setTotal(payload.total || 0)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => { load(); fetchCatalogueStatus().then(setCatalogueStatus).catch(() => {}) }, [])
  const update = (event) => setFilters({ ...filters, [event.target.name]: event.target.value })
  const sortedDevices = [...devices].sort((a, b) => sort === 'price' ? a.price - b.price : sort === 'performance' ? (b.benchmark?.overall_index || 0) - (a.benchmark?.overall_index || 0) : (b.security?.score || 0) - (a.security?.score || 0))
  const select = async (id) => { setError(''); try { const payload = await fetchDevice(id); setSelected(payload.item); setComparisons([]) } catch (err) { setError(err.message) } }
  const compare = async () => { if (!selected) return; try { const payload = await fetchComparisons(selected.id, { category: 'same', price_range: 'similar', performance: 'similar' }); setComparisons(payload.items || []) } catch (err) { setError(err.message) } }

  return <div className="app-shell">
    <header className="hero"><div className="eyebrow">BStudioB · Device decisions made clearer</div><h1>Choose a device you can trust.</h1><p>Search products, understand the trade-offs in plain English, and get a practical plan for making your device safer and faster.</p><button className="primary" onClick={() => document.getElementById('search')?.scrollIntoView({ behavior: 'smooth' })}>Start comparing</button></header>
    <main>
      <section id="search" className="search-panel"><div><span className="eyebrow">01 · Find a device</span><h2>Tell us what you need</h2><p className="muted">Start simple. You can add more detail when you know what matters.</p></div>
        <form onSubmit={(event) => { event.preventDefault(); load() }}>
          <label>Search by name or brand<input name="query" value={filters.query} onChange={update} placeholder="MacBook, ThinkPad, Surface…" maxLength="100" /></label>
          <label>Who is it for?<select name="use_case" value={filters.use_case} onChange={update}><option>Personal</option><option>Work</option><option>Government</option></select></label>
          <label>Device type<select name="category" value={filters.category} onChange={update}><option value="">Any type</option><option value="Laptops">Laptops</option><option value="PCs">Desktop PCs</option><option value="Tablet">Tablets</option></select></label>
          <label>Brand<select name="brand" value={filters.brand} onChange={update}><option value="">Any brand</option><option>Apple</option><option>Dell</option><option>HP</option><option>Lenovo</option><option>Microsoft</option></select></label>
          <label>Minimum RAM<input name="ram" type="number" min="0" max="128" value={filters.ram} onChange={update} /></label>
          <button className="primary" type="submit">{loading ? 'Loading…' : 'Search catalogue'}</button>
        </form>
      </section>
      {error && <div className="notice error" role="alert">{error}</div>}
      <section className="results"><div className="section-heading"><div><span className="eyebrow">02 · Shortlist</span><h2>{filters.query ? 'Search results' : 'Reviewed devices'}</h2></div><div className="result-controls"><span className="muted">{total} devices · {catalogueStatus?.live_scraping ? 'live provider data' : 'reviewed catalogue'}</span><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="security">Security first</option><option value="performance">Performance first</option><option value="price">Lowest price</option></select></label></div></div>
        {loading ? <div className="notice">Loading the reviewed catalogue…</div> : sortedDevices.length ? <div className="device-grid">{sortedDevices.map(device => <DeviceCard key={device.id} device={device} onSelect={select} />)}</div> : <div className="notice">No devices matched these filters. Try removing one filter.</div>}
      </section>
      {selected && <DeviceDetail device={selected} comparisons={comparisons} onCompare={compare} onClose={() => setSelected(null)} />}
    </main>
    <footer>The catalogue is guidance, not certification. Prices and availability must be checked before purchase.</footer>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
