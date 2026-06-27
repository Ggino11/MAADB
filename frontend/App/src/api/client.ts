const BASE_URL = '/api'

export async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`Errore ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function postJSON<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`Errore ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  getPerson:          (id: string) => fetchJSON(`/lookup/person/${id}`),
  getTransferChain:   (id: string, hops: number) => fetchJSON(`/lookup/account/${id}/transfers?hops=${hops}`),
  getCompanyPortfolio:(id: string) => fetchJSON(`/lookup/company/${id}/portfolio`),
  getCompanyStats:    () => fetchJSON(`/analytics/companies/stats`),
  getShortestPath:    (from: string, to: string) => fetchJSON(`/analytics/network/shortest-path?from_id=${from}&to_id=${to}`),
  getLaunderingCycle: (id: string, depth: number) => fetchJSON(`/analytics/suspicious-cycle/${id}?depth=${depth}`),
  getFlagged:         () => fetchJSON(`/flagged/`),
  flagAccount:        (body: object) => postJSON(`/flagged/`, body),
  removeFlag:         (id: string) => fetch(`/api/flagged/${id}`, { method: 'DELETE' }),
}
