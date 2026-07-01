/**
 * Client HTTP per le chiamate all'API del backend.
 *
 * Tutte le richieste usano `BASE_URL` come prefisso, così da essere
 * intercettate dal proxy di Vite in sviluppo e indirizzate al server
 * FastAPI senza problemi di CORS.
 */

/** Prefisso comune a tutti gli endpoint del backend. */
const BASE_URL = '/api'

/**
 * Esegue una richiesta GET verso il backend e deserializza la risposta JSON.
 *
 * @template T - Tipo atteso della risposta JSON (default: `any`).
 * @param path - Percorso relativo a `BASE_URL` (es. `/search/person?q=Mario`).
 * @returns Una `Promise` che si risolve con i dati deserializzati.
 * @throws {Error} Se la risposta HTTP non è OK (status >= 400).
 */
export async function fetchJSON<T = any>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`Errore ${res.status}: ${res.statusText}`)
  return res.json()
}

/**
 * Esegue una richiesta POST verso il backend con corpo JSON e
 * deserializza la risposta JSON.
 *
 * @template T - Tipo atteso della risposta JSON (default: `any`).
 * @param path - Percorso relativo a `BASE_URL` (es. `/analytics/...`).
 * @param body - Oggetto da serializzare come corpo della richiesta.
 * @returns Una `Promise` che si risolve con i dati deserializzati.
 * @throws {Error} Se la risposta HTTP non è OK (status >= 400).
 */
export async function postJSON<T = any>(path: string, body: object): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`Errore ${res.status}: ${res.statusText}`)
  return res.json()
}

/**
 * Raccolta dei metodi tipizzati per interagire con gli endpoint del backend.
 * Ogni metodo wrappa `fetchJSON` o `postJSON` con il percorso corretto.
 */
export const api = {
  /**
   * Cerca entità (persone, aziende, conti) per tipo e testo libero.
   * @param type - Tipo di entità (`person`, `company`, `account`, …).
   * @param q    - Stringa di ricerca (verrà URL-encoded automaticamente).
   */
  searchEntities: (type: string, q: string) =>
    fetchJSON(`/search/${type}?q=${encodeURIComponent(q)}`),

  /**
   * Recupera il profilo completo di una persona tramite il suo ID.
   * @param id - Identificatore univoco della persona nel database.
   */
  getPerson: (id: string) =>
    fetchJSON(`/lookup/person/${id}`),

  /**
   * Restituisce la catena di trasferimenti associata a un conto bancario.
   * @param id   - Identificatore del conto.
   * @param hops - Numero massimo di salti (hop) da esplorare nel grafo.
   */
  getTransferChain: (id: string, hops: number) =>
    fetchJSON(`/lookup/account/${id}/transfers?hops=${hops}`),

  /**
   * Recupera il portafoglio (conti e investimenti) di un'azienda.
   * @param id - Identificatore univoco dell'azienda.
   */
  getCompanyPortfolio: (id: string) =>
    fetchJSON(`/lookup/company/${id}/portfolio`),

  /**
   * Restituisce statistiche aggregate su tutte le aziende presenti nel sistema.
   */
  getCompanyStats: () =>
    fetchJSON(`/analytics/companies/stats`),

  /**
   * Calcola il percorso più breve tra due nodi del grafo finanziario.
   * @param from - ID del nodo di partenza.
   * @param to   - ID del nodo di destinazione.
   */
  getShortestPath: (from: string, to: string) =>
    fetchJSON(`/analytics/network/shortest-path?from_id=${from}&to_id=${to}`),

  /**
   * Individua cicli sospetti di riciclaggio di denaro a partire da un nodo.
   * @param id    - ID del nodo da cui iniziare l'analisi.
   * @param depth - Profondità massima dell'esplorazione nel grafo.
   */
  getLaunderingCycle: (id: string, depth: number) =>
    fetchJSON(`/analytics/suspicious-cycle/${id}?depth=${depth}`),
}
