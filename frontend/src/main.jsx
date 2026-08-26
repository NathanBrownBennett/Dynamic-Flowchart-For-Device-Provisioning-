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

function routeFromHash() {
  const hash = window.location.hash.replace(/^#/, '')
  if (hash === 'guide') return { view: 'guide', id: null }
  if (hash.startsWith('device/')) return { view: 'detail', id: Number(hash.split('/')[1]) || null }
  return { view: 'browse', id: null }
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

function formatPrice(offer) {
  const value = offer?.total_price ?? offer?.price
  if (value == null) return 'Price not verified'
  const prefix = offer.currency === 'GBP' ? '£' : `${offer.currency || ''} `
  return `${prefix}${Number(value).toLocaleString()}${offer.total_price_complete ? '' : ' + delivery if applicable'}`
}

function currentOffer(device) {
  return (device.offers || []).find((offer) => offer.total_price != null || offer.price != null)
}

function catalogueStateLabel(status) {
  if (status?.catalogue_state === 'current' && status?.catalogue_mode === 'retailer_observation') return 'Current retailer observations'
  const labels = { current: 'Current provider feed', partial: 'Catalogue current · prices incomplete', sample: 'Local fixture mode', stale: 'Catalogue needs refresh', unavailable: 'Live catalogue unavailable', empty: 'No live catalogue loaded' }
  return labels[status?.catalogue_state] || 'Evidence status loading'
}

function offerFreshness(offer) {
  if (!offer.checked_at) return 'No check date'
  if (offer.expires_at && new Date(offer.expires_at) < new Date()) return 'Price may be stale'
  return `Checked ${offer.checked_at.slice(0, 10)}`
}

function VendorOffers({ device }) {
  const offers = device.offers || []
  if (!offers.length) return <section className="comparison-box vendor-box"><div className="section-heading"><div><h3>Where to buy</h3><p className="small-note">No approved live vendor price feed is attached to this device yet.</p></div></div><div className="retailer-list">{(device.vendor_links || []).map((vendor) => <a key={vendor.vendor} href={vendor.url} target="_blank" rel="noreferrer noopener">Search {vendor.vendor}</a>)}</div><p className="small-note vendor-warning">These are vendor search links, not verified offers, so they are not ranked by price.</p></section>
  return <section className="comparison-box vendor-box"><div className="section-heading"><div><h3>Vendor offers</h3><p className="small-note">Observed offers are sorted by total known cost. Verify stock and final price on the retailer site.</p></div><span className="offer-count">{offers.length} checked</span></div><div className="offer-list">{offers.map((offer, index) => <a className="offer-row" key={`${offer.vendor}-${offer.url}`} href={offer.url} target="_blank" rel="noreferrer noopener"><span className="offer-rank">{index + 1}</span><span className="offer-vendor"><strong>{offer.vendor}</strong><small>{offer.availability} · {offerFreshness(offer)}{offer.is_affiliate ? ' · affiliate link' : ''}{offer.is_sponsored ? ' · sponsored' : ''}</small></span><strong className="offer-price">{formatPrice(offer)} <span>↗</span></strong></a>)}</div></section>
}

function DeviceCard({ device, onSelect }) {
  const score = device.security?.score ?? 0
  const level = device.security?.level || 'Unrated'
  const offer = currentOffer(device)
  return <article className="device-card">
    <div className="device-card-top">
      {device.image && <img className="device-thumb" src={device.image} alt={`${device.name} thumbnail`} loading="lazy" />}
      <div><span className="eyebrow">{device.category}</span><h3>{device.name}</h3></div>
      <span className={`score score-${level.toLowerCase()}`}>{score}%</span>
    </div>
    <p className="muted">{device.os} · {device.ram} GB RAM · {device.storage} GB storage</p>
    <p className="plain-score"><strong>{level} security baseline.</strong> {scoreCopy(level, score)}</p>
    <p className="small-note">{device.catalogue?.source || 'Source unavailable'} · {freshnessLabel(device.catalogue)}</p>
    <div className="card-footer"><strong>{offer ? formatPrice(offer) : 'Price not currently verified'}</strong><button onClick={() => onSelect(device.id)}>Review device</button></div>
  </article>
}

function Metric({ label, value }) {
  return <span className="metric"><small>{label}</small><strong>{value}</strong></span>
}

function DetailTabs({ active, onChange }) {
  return <div className="detail-tabs" role="tablist" aria-label="Device review sections">
    {[['overview', 'Overview'], ['security', 'Security'], ['performance', 'Performance'], ['vendors', 'Vendors']].map(([id, label]) => <button key={id} role="tab" aria-selected={active === id} className={active === id ? 'active' : ''} onClick={() => onChange(id)}>{label}</button>)}
  </div>
}

function DeviceDetail({ device, comparisons, context, detailTab, onTabChange, onCompare, onBack }) {
  const security = device.security || {}
  const benchmark = device.benchmark || {}
  const tools = device.debloat_tools || []
  const catalogue = device.catalogue || {}
  const downloadSummary = () => {
    const summary = [
      `Device Provisioning Toolkit decision summary`, `Device: ${device.name}`,
      `Context: ${context.use_case}${context.work_profile ? ` · ${context.work_profile}` : ''}`,
      `Security: ${security.score ?? 0}% · ${security.level || 'Unrated'}`,
      `Performance index: ${benchmark.overall_index ?? 0}/100`,
      `Lowest verified total price: ${currentOffer(device) ? formatPrice(currentOffer(device)) : 'not currently verified'}`,
      `Catalogue source: ${catalogue.source || 'unknown'}`, `Retrieved: ${catalogue.retrieved_at || 'unknown'}`, `Expires: ${catalogue.expires_at || 'unknown'}`,
      '', 'Limitations:', ...(security.limitations || ['Heuristic comparison only.']), '', 'Review the source and organisation requirements before purchase or deployment.',
    ].join('\n')
    const blob = new Blob([summary], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = `device-decision-${device.id}.txt`; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
  }
  return <section className="detail-view" aria-labelledby="device-review-heading">
    <div className="back-row"><button className="back-button" onClick={onBack}>← Back to recommendations</button><span className="eyebrow">Device review</span></div>
    <div className="detail-title"><div><h1 id="device-review-heading">{device.name}</h1><p className="lead">{device.os} · {device.cpu_vendor} · {device.category}</p></div><button className="secondary" onClick={downloadSummary}>Download summary</button></div>
    <div className="context-row"><div className="context-pill">Recommendation for: <strong>{context.use_case === 'Work' ? 'Business' : context.use_case}</strong>{context.work_profile && context.use_case === 'Work' ? ` · ${context.work_profile.replaceAll('_', ' ')}` : ''}</div><span className="freshness-note">{catalogue.source || 'Source unavailable'} · {freshnessLabel(catalogue)}</span></div>
    <div className="metric-row"><Metric label="Security score" value={`${security.score ?? 0}% · ${security.level || 'Unrated'}`} /><Metric label="Lowest verified total" value={currentOffer(device) ? formatPrice(currentOffer(device)) : 'Not verified'} /><Metric label="Memory" value={`${device.ram} GB`} /><Metric label="Storage" value={`${device.storage} GB`} /></div>
    <DetailTabs active={detailTab} onChange={onTabChange} />
    <div className="detail-content">
      {detailTab === 'overview' && <div className="detail-column overview-column">
        <section className="guidance-block"><h2>What this means</h2><p>{device.experience?.summary || scoreCopy(security.level, security.score ?? 0)}</p><div className="rating-strip"><span>OS <strong>{security.os_rating ?? 0}</strong></span><span>Hardware <strong>{security.hardware_rating ?? 0}</strong></span><span>Performance <strong>{benchmark.overall_index ?? 0}</strong></span></div><p className="small-note">{device.experience?.os_context || 'Scores are a practical comparison aid, not certification.'}</p></section>
        <section className="comparison-box"><h2>Evidence and limits</h2><p className="small-note">Evidence quality: <strong>{security.evidence_quality || catalogue.evidence_quality || 'unknown'}</strong> · Score version: {security.score_version || 'not supplied'}</p><ul>{(security.limitations || []).slice(0, 3).map((item, index) => <li key={index}>{item}</li>)}</ul><button className="text-button" onClick={() => onTabChange('security')}>See full security evidence →</button></section>
        <section className="comparison-box alternatives"><div className="section-heading"><div><h2>Similar choices</h2><p className="small-note">Compare nearby options with similar price and performance.</p></div><button className="secondary" onClick={onCompare}>Find alternatives</button></div>{comparisons.length ? <div className="mini-grid">{comparisons.map(item => <div className="mini-card" key={item.id}><strong>{item.name}</strong><span>£{item.price} · {item.security?.score}% security score</span></div>)}</div> : <p className="small-note">Choose “Find alternatives” to load comparisons.</p>}</section>
      </div>}
      {detailTab === 'security' && <div className="detail-column"><section className="guidance-block"><h2>Security score breakdown</h2><div className="factor-list">{(security.score_factors || []).map((factor) => <div className="factor-row" key={factor.id}><span><strong>{factor.label}</strong><small>{factor.explanation}</small></span><b className={factor.points < 0 ? 'negative' : ''}>{factor.points > 0 ? '+' : ''}{factor.points}</b></div>)}</div></section><section className="guidance-block"><h2>Do these things first</h2><ul>{(security.recommendations?.settings || []).slice(0, 8).map((item, index) => <li key={index}>{item}</li>)}</ul></section><section className="guidance-block"><h2>Risks to understand</h2>{(security.findings || []).length ? <ul>{security.findings.slice(0, 6).map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No specific risk was flagged by the current rules. Keep the normal update, encryption and account-safety steps.</p>}</section><section className="comparison-box"><h2>Security evidence</h2>{device.security_evidence?.length ? <ul>{device.security_evidence.slice(0, 8).map((item) => <li key={`${item.provider}-${item.cve_id}-${item.checked_at}`}>{item.cve_id || item.provider}: {item.summary || 'security evidence recorded'} · {item.confidence}</li>)}</ul> : <p className="small-note">No model-specific vulnerability evidence is attached yet; the score remains heuristic.</p>}</section></div>}
      {detailTab === 'performance' && <div className="detail-column"><section className="comparison-box"><h2>Performance at a glance</h2><div className="benchmark-grid"><Metric label="Overall" value={`${benchmark.overall_index ?? 0}/100`} /><Metric label="CPU" value={`${benchmark.cpu_index ?? 0}/100`} /><Metric label="Memory" value={`${benchmark.memory_index ?? 0}/100`} /><Metric label="Storage" value={`${benchmark.storage_index ?? 0}/100`} /></div><p className="small-note">Evidence state: {device.data_quality?.benchmark_state || 'unknown'}. These are normalized specification comparisons, not laboratory results.</p>{device.benchmark_evidence?.length ? <ul>{device.benchmark_evidence.slice(0, 5).map((item) => <li key={`${item.suite}-${item.tested_at}`}>{item.suite} {item.version || ''}: {item.score ?? 'unscored'} · {item.evidence_type}{item.source_url && <> · <a href={item.source_url} target="_blank" rel="noreferrer noopener">source</a></>}</li>)}</ul> : <p className="small-note">No independent benchmark record is attached to this device.</p>}</section><section className="comparison-box"><h2>Improve performance</h2><p className="small-note">{device.experience?.summary || 'Keep the operating system updated and leave enough free storage for updates.'}</p>{device.experience?.strengths?.length ? <ul>{device.experience.strengths.map((item) => <li key={item}>{item}</li>)}</ul> : null}{device.experience?.tradeoffs?.length ? <p className="small-note"><strong>Plan for:</strong> {device.experience.tradeoffs.join(' · ')}</p> : null}{tools.length ? <div className="tool-list">{tools.slice(0, 4).map((tool, index) => <a key={index} href={tool.url} target="_blank" rel="noreferrer noopener"><strong>{tool.name}</strong><span>{tool.description}</span></a>)}</div> : null}</section></div>}
      {detailTab === 'vendors' && <div className="detail-column"><VendorOffers device={device} /><section className="comparison-box"><h2>Support and ownership</h2><p className="small-note">Support until: {catalogue.support_until || 'not supplied'} · Warranty: {catalogue.warranty || 'not supplied'} · Image licence: {catalogue.image_license || 'not supplied'}</p></section></div>}
    </div>
  </section>
}

function Guide() {
  return <section className="guide-view"><div className="view-heading"><span className="eyebrow">How the toolkit works</span><h1>Simple decisions, clearly explained.</h1><p className="lead">The toolkit helps you narrow a device choice, then shows what is known, what is estimated and what you should do next.</p></div><div className="guide-grid"><article><span className="guide-number">1</span><h2>Choose your situation</h2><p>Home, business or public-sector use changes the risks and priorities. Start with the situation that best matches the device.</p></article><article><span className="guide-number">2</span><h2>Compare the shortlist</h2><p>Devices are ranked by your chosen priority. Scores are comparison aids, not security certification or a promise of perfect performance.</p></article><article><span className="guide-number">3</span><h2>Review the evidence</h2><p>Open a device to see the OS, hardware, performance and security breakdown in plain English, with dates and limitations.</p></article><article><span className="guide-number">4</span><h2>Harden before use</h2><p>Follow the first-step settings, update, encryption and account-safety guidance before connecting the device to important data.</p></article></div><div className="notice guide-note"><strong>About live data.</strong> Prices, availability, benchmarks and vulnerability evidence only appear when an approved source supplies them. The pilot does not invent missing facts.</div></section>
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
  const [detailTab, setDetailTab] = useState('overview')
  const [route, setRoute] = useState(routeFromHash())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const context = useMemo(() => filters.use_case === 'Work' ? { use_case: filters.use_case, work_profile: filters.work_profile } : { use_case: filters.use_case }, [filters.use_case, filters.work_profile])
  const navigate = (view, id = null) => { window.location.hash = view === 'detail' ? `device/${id}` : view; setRoute({ view, id }) }
  const load = async (values = filters) => {
    setLoading(true); setError('')
    try {
      const payload = values.query ? await searchDevices(values) : await fetchDevices(values)
      setDevices(payload.items || []); setTotal(payload.total || 0)
      const params = new URLSearchParams(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '' && value !== 0)))
      window.history.replaceState({}, '', `${window.location.pathname}?${params}${window.location.hash}`)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => {
    const onHashChange = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', onHashChange)
    load(); fetchCatalogueStatus().then(setCatalogueStatus).catch(() => {}); fetchCriteria().then((payload) => setCriteria({ ...fallbackCriteria, ...payload })).catch(() => {})
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  useEffect(() => {
    if (route.view === 'detail' && route.id && (!selected || selected.id !== route.id)) select(route.id)
  }, [route.view, route.id])
  const update = (event) => setFilters({ ...filters, [event.target.name]: event.target.value })
  const sortedDevices = [...devices].sort((a, b) => { const price = (device) => currentOffer(device)?.total_price ?? currentOffer(device)?.price ?? Number.POSITIVE_INFINITY; return sort === 'price' ? price(a) - price(b) : sort === 'performance' ? (b.benchmark?.overall_index || 0) - (a.benchmark?.overall_index || 0) : (b.security?.score || 0) - (a.security?.score || 0) })
  const select = async (id) => { setError(''); try { const payload = await fetchDevice(id, context); setSelected(payload.item); setComparisons([]); setDetailTab('overview'); navigate('detail', id) } catch (err) { setError(err.message) } }
  const compare = async () => { if (!selected) return; try { const payload = await fetchComparisons(selected.id, { category: 'same', price_range: 'similar', performance: 'similar', ...context }); setComparisons(payload.items || []) } catch (err) { setError(err.message) } }
  const chooseUseCase = (useCase) => setFilters({ ...filters, use_case: useCase })

  return <div className="app-shell">
    <header className="app-bar"><a className="brand" href="#browse" onClick={() => navigate('browse')}><span className="brand-mark">✦</span><span><strong>Device Provisioning</strong><small>Toolkit by BStudioB</small></span></a><nav className="primary-nav" aria-label="Primary navigation"><button className={route.view === 'browse' ? 'active' : ''} onClick={() => navigate('browse')}>Browse devices</button><button className={route.view === 'guide' ? 'active' : ''} onClick={() => navigate('guide')}>How scoring works</button></nav><span className="pilot-badge"><span className="pilot-full">Invite-only pilot</span><span className="pilot-short">Pilot</span></span></header>
    <main className="page-shell">
      {route.view === 'guide' && <Guide />}
      {route.view === 'detail' && selected && <DeviceDetail device={selected} comparisons={comparisons} context={context} detailTab={detailTab} onTabChange={setDetailTab} onCompare={compare} onBack={() => navigate('browse')} />}
      {route.view === 'detail' && !selected && <div className="notice">Loading this device review…</div>}
      {route.view === 'browse' && <>
        <section className="browse-intro"><div><span className="eyebrow">Safer device decisions</span><h1>Find a device that fits.</h1><p>Compare devices for home, business or public-sector use. See the security trade-offs and practical steps in plain English.</p></div><div className="status-panel"><strong>{catalogueStateLabel(catalogueStatus)}</strong><span>{catalogueStatus?.product_count ?? '—'} products · {catalogueStatus?.current_offer_count ?? 0} observed offers</span><small>Prices and evidence are labelled by freshness.</small></div></section>
        <section className="context-strip" aria-label="Choose your situation"><span className="context-label">I’m choosing for</span><div className="context-options"><button className={filters.use_case === 'Personal' ? 'selected' : ''} onClick={() => chooseUseCase('Personal')}>Home & personal</button><button className={filters.use_case === 'Work' ? 'selected' : ''} onClick={() => chooseUseCase('Work')}>Small business</button><button className={filters.use_case === 'Government' ? 'selected' : ''} onClick={() => chooseUseCase('Government')}>Public sector</button></div><button className="guide-link" onClick={() => navigate('guide')}>How it works →</button></section>
        <section className="search-panel"><div className="panel-heading"><div><span className="eyebrow">Find a shortlist</span><h2>Tell us what you need</h2></div><span className="step-label">1 of 2</span></div><form onSubmit={(event) => { event.preventDefault(); load() }}>
          <div className="quick-fields"><label>What matters most?<select value={priority} onChange={(event) => { setPriority(event.target.value); setSort(event.target.value) }}><option value="security">Security baseline</option><option value="performance">Performance</option><option value="price">Lower price</option></select></label>
          {filters.use_case === 'Work' && <label>Work role<select name="work_profile" value={filters.work_profile} onChange={update}>{criteria.work_profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.label}</option>)}</select></label>}
          <label>Search by name or brand<input name="query" value={filters.query} onChange={update} placeholder="MacBook, ThinkPad, Surface…" maxLength="100" /></label></div>
          <button className="primary" type="submit">{loading ? 'Loading…' : 'Show recommendations'} <span>→</span></button>
          <details className="advanced-filters" open><summary>More filters <span>Adjust device type, brand, OS and minimum specifications</span></summary><div className="advanced-grid"><label>Device type<select name="category" value={filters.category} onChange={update}><option value="">Any type</option>{criteria.categories.map(category => <option key={category}>{category}</option>)}</select></label>
          <label>Brand<select name="brand" value={filters.brand} onChange={update}><option value="">Any brand</option>{criteria.brands.map(brand => <option key={brand}>{brand}</option>)}</select></label>
          <label>Operating system<select name="operating_system" value={filters.operating_system} onChange={update}><option value="">Any OS</option>{criteria.operating_systems.map(os => <option key={os}>{os}</option>)}</select></label>
          <label>Maximum price (£)<input name="price_max" type="number" min="0" max="100000" value={filters.price_max} onChange={update} /></label><label>Minimum RAM (GB)<input name="ram" type="number" min="0" max="128" value={filters.ram} onChange={update} /></label><label>Minimum storage (GB)<input name="storage" type="number" min="0" max="100000" value={filters.storage} onChange={update} /></label></div></details>
        </form></section>
        {error && <div className="notice error" role="alert">{error}</div>}
        <section className="results"><div className="section-heading"><div><span className="eyebrow">Your shortlist</span><h2>{filters.query ? 'Search results' : 'Reviewed devices'}</h2><p className="muted">For {filters.use_case === 'Work' ? 'business' : filters.use_case.toLowerCase()} use · {total} devices found</p></div><div className="result-controls"><span className="catalogue-chip"><i /> {catalogueStateLabel(catalogueStatus)}</span><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="security">Security first</option><option value="performance">Performance first</option><option value="price">Lowest observed price</option></select></label></div></div>
          {catalogueStatus && ['empty', 'unavailable', 'stale'].includes(catalogueStatus.catalogue_state) && <div className="notice warning"><strong>{catalogueStateLabel(catalogueStatus)}.</strong> This interface will not invent prices, benchmark results or product photographs. An approved feed must be loaded before the service can make live recommendations.</div>}
          {catalogueStatus?.catalogue_mode === 'retailer_observation' && catalogueStatus.catalogue_state === 'current' && <div className="notice"><strong>Live retailer observations.</strong> Prices, stock and product details can change; confirm them on the linked retailer page before buying.</div>}
          {loading ? <div className="notice">Loading the reviewed catalogue…</div> : sortedDevices.length ? <div className="device-grid">{sortedDevices.map(device => <DeviceCard key={device.id} device={device} onSelect={select} />)}</div> : <div className="notice">No devices matched these choices. Try increasing the budget or removing one filter.</div>}
        </section>
      </>}
    </main>
    <footer><p>The catalogue is guidance, not certification. Prices and availability must be checked before purchase.</p><p>This is an invite-only pilot. No public account or sign-up data is collected here.</p></footer>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
