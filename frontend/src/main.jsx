import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { fetchCatalogueStatus, fetchComparisons, fetchCriteria, fetchDevice, fetchDevices, searchDevices } from './api'
import './styles.css'

const initialFilters = {
  query: '', category: '', brand: '', operating_system: '', use_case: 'Personal',
  work_profile: 'general_office', price_min: 0, price_max: 3000,
  cpu_speed: 0, ram: 0, storage: 0, screen_size: 0,
}

const fallbackCriteria = {
  categories: ['Laptops', 'PCs', 'Tablet'],
  brands: ['Apple', 'Dell', 'HP', 'Lenovo', 'Microsoft'],
  operating_systems: ['Windows 11', 'macOS', 'ChromeOS', 'Android', 'iPadOS', 'Linux'],
  work_profiles: [
    { id: 'general_office', label: 'General office' },
    { id: 'remote_worker', label: 'Remote worker' },
    { id: 'developer', label: 'Developer or technical user' },
    { id: 'privileged_admin', label: 'Privileged administrator' },
    { id: 'field_worker', label: 'Field or mobile worker' },
  ],
}

function scoreCopy(level, score) {
  if (level === 'Excellent') return `Strong baseline (${score}%). Good fit for most everyday setups.`
  if (level === 'Good') return `A sensible baseline (${score}%). Review the suggested controls before deployment.`
  if (level === 'Adequate') return `Usable with care (${score}%). Plan updates, encryption and account protection.`
  return `Extra care needed (${score}%). Check the risks before choosing this device.`
}

function freshnessLabel(catalogue) {
  if (!catalogue?.expires_at) return 'Freshness date not supplied'
  const expires = new Date(catalogue.expires_at)
  return expires < new Date() ? 'This price observation may be stale' : `Checked until ${catalogue.expires_at.slice(0, 10)}`
}

function DeviceCard({ device, onSelect }) {
  const score = device.security?.score ?? 0
  const level = device.security?.level || 'Unrated'
  return <article className="device-card">
    <div className="device-card-top">
      {device.image && <img className="device-thumb" src={device.image} alt={`${device.name} thumbnail`} loading="lazy" />}
      <div><span className="eyebrow">{device.category}</span><h3>{device.name}</h3></div>
      <span className={`score score-${level.toLowerCase()}`}>{score}%</span>
    </div>
    <p className="muted">{device.os} · {device.ram} GB RAM · {device.storage} GB storage</p>
    <p className="plain-score"><strong>{level} security baseline.</strong> {scoreCopy(level, score)}</p>
    <p className="small-note">{device.catalogue?.source || 'Curated local catalogue'} · {freshnessLabel(device.catalogue)}</p>
    <div className="card-footer"><strong>£{Number(device.price).toLocaleString()}</strong><button onClick={() => onSelect(device.id)}>Review device</button></div>
  </article>
}

function Metric({ label, value }) {
  return <span className="metric"><small>{label}</small><strong>{value}</strong></span>
}

function DeviceDetail({ device, comparisons, context, onCompare, onClose }) {
  const security = device.security || {}
  const benchmark = device.benchmark || {}
  const tools = device.debloat_tools || []
  const catalogue = device.catalogue || {}
  const downloadSummary = () => {
    const summary = [
      `Device Provisioning Toolkit decision summary`,
      `Device: ${device.name}`,
      `Context: ${context.use_case}${context.work_profile ? ` · ${context.work_profile}` : ''}`,
      `Security: ${security.score ?? 0}% · ${security.level || 'Unrated'}`,
      `Performance index: ${benchmark.overall_index ?? 0}/100`,
      `Price observed: £${device.price}`,
      `Catalogue source: ${catalogue.source || 'unknown'}`,
      `Retrieved: ${catalogue.retrieved_at || 'unknown'}`,
      `Expires: ${catalogue.expires_at || 'unknown'}`,
      '',
      'Limitations:',
      ...(security.limitations || ['Heuristic comparison only.']),
      '',
      'Review the source and organisation requirements before purchase or deployment.',
    ].join('\n')
    const blob = new Blob([summary], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `device-decision-${device.id}.txt`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  return <section className="detail-panel" aria-labelledby="device-review-heading">
    <div className="section-heading"><div><span className="eyebrow">03 · Device review</span><h2 id="device-review-heading">{device.name}</h2><p className="lead">{device.os} · {device.cpu_vendor} · {device.category}</p></div><button className="quiet" onClick={onClose}>Close</button></div>
    <div className="context-row"><div className="context-pill">Recommendation for: <strong>{context.use_case === 'Work' ? 'Business' : context.use_case}</strong>{context.work_profile && context.use_case === 'Work' ? ` · ${context.work_profile.replaceAll('_', ' ')}` : ''}</div><button className="secondary" onClick={downloadSummary}>Download decision summary</button></div>
    <div className="metric-row"><Metric label="Security score" value={`${security.score ?? 0}% · ${security.level || 'Unrated'}`} /><Metric label="Price shown" value={`£${device.price}`} /><Metric label="Memory" value={`${device.ram} GB`} /><Metric label="Storage" value={`${device.storage} GB`} /></div>
    <p className="freshness-note">Source: <strong>{catalogue.source || 'Curated local catalogue'}</strong> · {freshnessLabel(catalogue)} · Availability: {catalogue.availability || 'unknown'}</p>
    <div className="detail-grid">
      <div className="detail-column">
        <section className="guidance-block"><h3>What this means</h3><p>{scoreCopy(security.level, security.score ?? 0)}</p><p className="small-note">This is a practical comparison aid, not a security certification or a guarantee.</p></section>
        <section className="guidance-block"><h3>Do these things first</h3><ul>{(security.recommendations?.settings || []).slice(0, 8).map((item, index) => <li key={index}>{item}</li>)}</ul></section>
        <section className="guidance-block"><h3>Risks to understand</h3>{(security.findings || []).length ? <ul>{security.findings.slice(0, 6).map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No specific risk was flagged by the current rules. Keep the normal update, encryption and account-safety steps.</p>}</section>
      </div>
      <div className="detail-column">
        <section className="comparison-box"><h3>Performance at a glance</h3><div className="benchmark-grid"><Metric label="Overall" value={`${benchmark.overall_index ?? 0}/100`} /><Metric label="CPU" value={`${benchmark.cpu_index ?? 0}/100`} /><Metric label="Memory" value={`${benchmark.memory_index ?? 0}/100`} /><Metric label="Storage" value={`${benchmark.storage_index ?? 0}/100`} /></div><p className="small-note">These are normalized comparisons based on catalogue data, not laboratory benchmarks.</p></section>
        <section className="comparison-box"><h3>Evidence and limits</h3><p className="small-note">Evidence quality: <strong>{security.evidence_quality || catalogue.evidence_quality || 'unknown'}</strong> · Score version: {security.score_version || 'not supplied'}</p><ul>{(security.limitations || []).map((item, index) => <li key={index}>{item}</li>)}</ul>{catalogue.evidence_url && <a href={catalogue.evidence_url} target="_blank" rel="noreferrer noopener">View product evidence</a>}</section>
        <section className="comparison-box"><h3>Support and ownership</h3><p className="small-note">Support until: {catalogue.support_until || 'not supplied'} · Warranty: {catalogue.warranty || 'not supplied'} · Image licence: {catalogue.image_license || 'not supplied'}</p></section>
        <section className="comparison-box"><h3>Improve performance</h3>{tools.length ? <div className="tool-list">{tools.slice(0, 4).map((tool, index) => <a key={index} href={tool.url} target="_blank" rel="noreferrer noopener"><strong>{tool.name}</strong><span>{tool.description}</span></a>)}</div> : <p>Keep the operating system updated, remove unused software and leave enough free storage for updates.</p>}</section>
        <section className="comparison-box"><h3>Where to compare prices</h3><p className="small-note">Prices and availability can change. Verify the final details before buying.</p><div className="retailer-list">{Object.entries(device.retailer_links || {}).slice(0, 6).map(([name, url]) => <a key={name} href={url} target="_blank" rel="noreferrer noopener">{name}</a>)}</div></section>
      </div>
    </div>
    <section className="comparison-box alternatives"><div className="section-heading"><div><h3>Similar choices</h3><p className="small-note">Compare nearby options with similar price and performance.</p></div><button className="secondary" onClick={onCompare}>Find alternatives</button></div>{comparisons.length ? <div className="mini-grid">{comparisons.map(item => <div className="mini-card" key={item.id}><strong>{item.name}</strong><span>£{item.price} · {item.security?.score}% security score</span></div>)}</div> : <p className="small-note">Choose “Find alternatives” to load comparisons.</p>}</section>
  </section>
}

function App() {
  const [filters, setFilters] = useState(initialFilters)
  const [priority, setPriority] = useState('security')
  const [criteria, setCriteria] = useState(fallbackCriteria)
  const [sort, setSort] = useState('security')
  const [devices, setDevices] = useState([])
  const [total, setTotal] = useState(0)
  const [catalogueStatus, setCatalogueStatus] = useState(null)
  const [selected, setSelected] = useState(null)
  const [comparisons, setComparisons] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const context = useMemo(() => filters.use_case === 'Work'
    ? { use_case: filters.use_case, work_profile: filters.work_profile }
    : { use_case: filters.use_case }, [filters.use_case, filters.work_profile])
  const load = async (values = filters) => {
    setLoading(true); setError('')
    try {
      const payload = values.query ? await searchDevices(values) : await fetchDevices(values)
      setDevices(payload.items || []); setTotal(payload.total || 0)
      const params = new URLSearchParams(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '' && value !== 0)))
      window.history.replaceState({}, '', `${window.location.pathname}?${params}`)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    fetchCatalogueStatus().then(setCatalogueStatus).catch(() => {})
    fetchCriteria().then((payload) => setCriteria({ ...fallbackCriteria, ...payload })).catch(() => {})
  }, [])
  const update = (event) => setFilters({ ...filters, [event.target.name]: event.target.value })
  const sortedDevices = [...devices].sort((a, b) => {
    return sort === 'price' ? a.price - b.price : sort === 'performance' ? (b.benchmark?.overall_index || 0) - (a.benchmark?.overall_index || 0) : (b.security?.score || 0) - (a.security?.score || 0)
  })
  const select = async (id) => { setError(''); try { const payload = await fetchDevice(id, context); setSelected(payload.item); setComparisons([]) } catch (err) { setError(err.message) } }
  const compare = async () => { if (!selected) return; try { const payload = await fetchComparisons(selected.id, { category: 'same', price_range: 'similar', performance: 'similar', ...context }); setComparisons(payload.items || []) } catch (err) { setError(err.message) } }
  const chooseUseCase = (useCase) => setFilters({ ...filters, use_case: useCase })

  return <div className="app-shell">
    <nav className="site-nav" aria-label="Primary navigation"><a className="brand" href="#top"><span className="brand-mark">✦</span><span><strong>Device Provisioning</strong><small>Toolkit by BStudioB</small></span></a><div className="nav-links"><a href="#search">Find a device</a><a href="#results">Recommendations</a><a href="#how-it-works">How it works</a></div><span className="pilot-badge">Invite-only pilot</span></nav>
    <header id="top" className="hero"><div className="hero-copy"><div className="eyebrow">BStudioB · Safer device decisions</div><h1>Choose the right device with confidence.</h1><p>Compare products, understand the security trade-offs and get plain-English steps to make your device safer and faster.</p><div className="hero-actions"><button className="primary" onClick={() => document.getElementById('search')?.scrollIntoView({ behavior: 'smooth' })}>Start comparing <span>→</span></button><a className="text-link" href="#how-it-works">See how it works</a></div><div className="hero-proof"><span>✓ Reviewed catalogue</span><span>✓ Security-aware scoring</span><span>✓ Plain-English guidance</span></div></div><div className="hero-visual" aria-label="Toolkit overview"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="security-card"><div className="card-kicker">DECISION SNAPSHOT</div><div className="shield-icon">✓</div><strong>Security baseline</strong><div className="score-ring"><span>94</span><small>/100</small></div><p>Clear evidence, practical controls and no confusing jargon.</p><div className="mini-status"><span><i /> Reviewed source</span><span><i /> Support checked</span></div></div></div></header>
    <main>
      <section id="how-it-works" className="intent-section"><div className="section-intro"><span className="eyebrow">Start with your situation</span><h2>One toolkit. Three ways to choose.</h2><p className="muted">Your context changes what “best” means. Pick a starting point and we’ll shape the recommendation around it.</p></div><div className="intent-grid"><button className={`intent-card ${filters.use_case === 'Personal' ? 'selected' : ''}`} onClick={() => chooseUseCase('Personal')}><span className="intent-icon">⌂</span><span><strong>Home & personal</strong><small>Everyday use, study and family devices</small></span><b>→</b></button><button className={`intent-card ${filters.use_case === 'Work' ? 'selected' : ''}`} onClick={() => chooseUseCase('Work')}><span className="intent-icon">▦</span><span><strong>Small business</strong><small>Work-ready devices with a safer baseline</small></span><b>→</b></button><button className={`intent-card ${filters.use_case === 'Government' ? 'selected' : ''}`} onClick={() => chooseUseCase('Government')}><span className="intent-icon">◇</span><span><strong>Public sector</strong><small>Exploratory comparisons for higher assurance needs</small></span><b>→</b></button></div></section>
      <section id="search" className="search-panel"><div><span className="eyebrow">01 · Find a device</span><h2>Tell us what you need</h2><p className="muted">Start with your situation. The service uses this context when explaining security and suitability.</p></div>
        <form onSubmit={(event) => { event.preventDefault(); load() }}>
          <label>What is it for?<select name="use_case" value={filters.use_case} onChange={update}><option value="Personal">Home or personal use</option><option value="Work">Small business or work</option><option value="Government">Government/public sector</option></select></label>
          {filters.use_case === 'Work' && <label>Work role<select name="work_profile" value={filters.work_profile} onChange={update}>{criteria.work_profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.label}</option>)}</select></label>}
          <label>What matters most?<select value={priority} onChange={(event) => { setPriority(event.target.value); setSort(event.target.value) }}><option value="security">Security baseline</option><option value="performance">Performance</option><option value="price">Lower price</option></select></label>
          <label>Search by name or brand<input name="query" value={filters.query} onChange={update} placeholder="MacBook, ThinkPad, Surface…" maxLength="100" /></label>
          <label>Device type<select name="category" value={filters.category} onChange={update}><option value="">Any type</option>{criteria.categories.map(category => <option key={category}>{category}</option>)}</select></label>
          <label>Brand<select name="brand" value={filters.brand} onChange={update}><option value="">Any brand</option>{criteria.brands.map(brand => <option key={brand}>{brand}</option>)}</select></label>
          <label>Operating system<select name="operating_system" value={filters.operating_system} onChange={update}><option value="">Any OS</option>{criteria.operating_systems.map(os => <option key={os}>{os}</option>)}</select></label>
          <label>Maximum price (£)<input name="price_max" type="number" min="0" max="100000" value={filters.price_max} onChange={update} /></label>
          <label>Minimum RAM (GB)<input name="ram" type="number" min="0" max="128" value={filters.ram} onChange={update} /></label>
          <label>Minimum storage (GB)<input name="storage" type="number" min="0" max="100000" value={filters.storage} onChange={update} /></label>
          <button className="primary" type="submit">{loading ? 'Loading…' : 'Show recommendations'}</button>
        </form>
      </section>
      {error && <div className="notice error" role="alert">{error}</div>}
      <section id="results" className="results"><div className="section-heading"><div><span className="eyebrow">02 · Shortlist</span><h2>{filters.query ? 'Search results' : 'Reviewed devices'}</h2><p className="muted">For {filters.use_case === 'Work' ? 'business' : filters.use_case.toLowerCase()} use · {total} devices found</p></div><div className="result-controls"><span className="catalogue-chip"><i /> {catalogueStatus?.live_scraping ? 'Live provider data' : 'Reviewed catalogue'}</span><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="security">Security first</option><option value="performance">Performance first</option><option value="price">Lowest price</option></select></label></div></div>
        {loading ? <div className="notice">Loading the reviewed catalogue…</div> : sortedDevices.length ? <div className="device-grid">{sortedDevices.map(device => <DeviceCard key={device.id} device={device} onSelect={select} />)}</div> : <div className="notice">No devices matched these choices. Try increasing the budget or removing one filter.</div>}
      </section>
      {selected && <DeviceDetail device={selected} comparisons={comparisons} context={context} onCompare={compare} onClose={() => setSelected(null)} />}
    </main>
    <footer><p>The catalogue is guidance, not certification. Prices and availability must be checked before purchase.</p><p>This is an invite-only pilot. To request access, use BStudioB’s existing approved contact channel; no public account or sign-up data is collected here.</p></footer>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
