const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { 'Accept': 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`)
  return payload
}

export const fetchDevices = (filters = {}) => api('/api/v1/devices?' + new URLSearchParams(filters))
export const fetchCatalogueStatus = () => api('/api/v1/catalogue/status')
export const fetchCriteria = () => api('/api/v1/criteria')
export const searchDevices = (filters) => api('/api/v1/search', { method: 'POST', body: JSON.stringify(filters) })
export const fetchDevice = (id, context = {}) => api(`/api/v1/devices/${id}?` + new URLSearchParams(context))
export const fetchComparisons = (id, filters) => api(`/api/v1/devices/${id}/comparisons?` + new URLSearchParams(filters))
