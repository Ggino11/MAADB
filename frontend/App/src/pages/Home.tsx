import { useState, useMemo, useEffect } from 'react'
import { api } from '../api/client'
import SearchableSelect from '../components/SearchableSelect'
import GraphViewer from '../components/GraphViewer'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

/* TYPES */

type PanelId = 'L1' | 'L2' | 'L3' | 'A1' | 'A2' | 'A3'

interface PanelMeta {
  id: PanelId
  title: string
  badge: string
  badgeColor: string
  badgeBg: string
}

interface HomeStats {
  total_persons: number
  total_accounts: number
  blocked_accounts: number
  total_companies: number
  blocked_companies: number
}

const PANELS: PanelMeta[] = [
  { id: 'L1', title: 'Anagrafica persona',           badge: 'MongoDB',  badgeColor: '#818cf8', badgeBg: 'rgba(79, 70, 229, 0.1)' },
  { id: 'L2', title: 'Trasferimenti account',         badge: 'Neo4j',    badgeColor: '#818cf8', badgeBg: 'rgba(79, 70, 229, 0.1)' },
  { id: 'L3', title: 'Portfolio azienda',              badge: 'Cross-DB', badgeColor: '#fbbf24', badgeBg: 'rgba(245, 158, 11, 0.1)' },
  { id: 'A1', title: 'Aziende bloccate per nazione',   badge: 'MongoDB',  badgeColor: '#818cf8', badgeBg: 'rgba(79, 70, 229, 0.1)' },
  { id: 'A2', title: 'Shortest path',                  badge: 'Neo4j',    badgeColor: '#818cf8', badgeBg: 'rgba(79, 70, 229, 0.1)' },
  { id: 'A3', title: 'Ciclo sospetto',                 badge: 'Cross-DB', badgeColor: '#fbbf24', badgeBg: 'rgba(245, 158, 11, 0.1)' },
]

/* HOME — Stats + Query Accordion*/

export default function Home() {
  const [stats, setStats] = useState<HomeStats | null>(null)
  const [openPanel, setOpenPanel] = useState<PanelId | null>(null)

  useEffect(() => {
    fetch('/api/home/stats').then((r) => r.json()).then(setStats)
  }, [])

  const toggle = (id: PanelId) => {
    setOpenPanel((prev) => (prev === id ? null : id))
  }

  return (
    <div style={{ padding: '40px 48px' }}>

      {/*Stats*/}
      {stats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 20, marginBottom: 48,
        }}>
          {([
            { label: 'Persone Totali',       value: stats.total_persons,     danger: false, accent: false },
            { label: 'Account Nel Grafo',    value: stats.total_accounts,    danger: false, accent: false },
            { label: 'Account Bloccati',     value: stats.blocked_accounts,  danger: true,  accent: false },
            { label: 'Aziende Bloccate',     value: stats.blocked_companies, danger: true,  accent: false },
          ] as const).map((m) => (
            <div key={m.label} style={{
              background: '#13131f', border: '1px solid #2a2a3a',
              borderRadius: 12, padding: '24px',
            }}>
              <div style={{
                fontSize: 13, color: '#64748b', marginBottom: 8, fontWeight: 500,
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>{m.label}</div>
              <div style={{
                fontSize: 32, fontWeight: 700,
                color: m.danger ? '#f87171' : m.accent ? '#34d399' : '#e2e8f0',
              }}>{m.value?.toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}

      {/* Query Console Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{
          fontSize: 32, fontWeight: 800, color: '#ffffff', marginBottom: 8,
          letterSpacing: '-0.02em',
        }}>
          Query Console
        </h1>
        <p style={{ color: '#94a3b8', fontSize: 15, lineHeight: 1.6 }}>
          Seleziona un modulo ed esegui la query direttamente da qui.
        </p>
      </div>

      {/* Accordion */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {PANELS.map((p) => (
          <AccordionItem
            key={p.id}
            meta={p}
            isOpen={openPanel === p.id}
            onToggle={() => toggle(p.id)}
          />
        ))}
      </div>
    </div>
  )
}

/* ACCORDION ITEM*/

function AccordionItem({ meta, isOpen, onToggle }: {
  meta: PanelMeta
  isOpen: boolean
  onToggle: () => void
}) {
  return (
    <div style={{
      background: '#13131f', border: '1px solid #2a2a3a', borderRadius: 12,
      transition: 'border-color 0.2s',
      borderColor: isOpen ? '#4f46e5' : '#2a2a3a',
    }}>
      {/* Header */}
      <button
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', background: 'transparent', color: '#f8fafc',
          border: 'none', cursor: 'pointer', fontSize: 15, fontWeight: 600,
          textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#64748b', fontSize: 13, fontWeight: 700, minWidth: 24 }}>{meta.id}</span>
          <span>{meta.title}</span>
          <span style={{
            fontSize: 10, padding: '3px 8px', borderRadius: 12,
            background: meta.badgeBg, color: meta.badgeColor,
            fontWeight: 600, letterSpacing: '0.05em',
          }}>
            {meta.badge}
          </span>
        </div>
        <span style={{
          transition: 'transform 0.2s', transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          fontSize: 18, color: '#64748b',
        }}>
          ▾
        </span>
      </button>

      {/* Body */}
      {isOpen && (
        <div style={{ padding: '4px 20px 20px', borderTop: '1px solid #2a2a3a' }}>
          <PanelBody panelId={meta.id} />
        </div>
      )}
    </div>
  )
}

/* PANEL BODY — dispatches to the correct sub-panel*/

function PanelBody({ panelId }: { panelId: PanelId }) {
  switch (panelId) {
    case 'L1': return <PanelL1 />
    case 'L2': return <PanelL2 />
    case 'L3': return <PanelL3 />
    case 'A1': return <PanelA1 />
    case 'A2': return <PanelA2 />
    case 'A3': return <PanelA3 />
  }
}

/* ── shared styles ─────────────────────────────────────── */
const formRow: React.CSSProperties = {
  display: 'flex', gap: 12, marginTop: 16, alignItems: 'center',
  flexWrap: 'wrap',
}
const resultBox: React.CSSProperties = {
  marginTop: 20, background: '#1a1a2e', borderRadius: 10,
  padding: 20, border: '1px solid #2a2a3a',
}
const errorBox: React.CSSProperties = {
  marginTop: 16, padding: 14, background: 'rgba(239, 68, 68, 0.1)',
  color: '#ef4444', borderRadius: 8, border: '1px solid rgba(239,68,68,0.25)',
  fontSize: 14,
}
const cellLabel: React.CSSProperties = {
  fontSize: 12, color: '#64748b', marginBottom: 4,
}
const cellValue: React.CSSProperties = {
  fontSize: 15, fontWeight: 500, color: '#e2e8f0',
}
const miniCard: React.CSSProperties = {
  background: '#13131f', padding: 16, borderRadius: 8,
  border: '1px solid #2a2a3a',
}
const thStyle: React.CSSProperties = {
  padding: '12px 20px', fontSize: 12, fontWeight: 600, color: '#64748b',
  textTransform: 'uppercase', textAlign: 'left',
}
const tdStyle: React.CSSProperties = {
  padding: '14px 20px', fontSize: 14, color: '#e2e8f0',
  borderBottom: '1px solid #2a2a3a',
}

/* L1 — Person Lookup (MongoDB)*/

function PanelL1() {
  const [personId, setPersonId] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (!personId) return
    setLoading(true); setError('')
    try {
      setResult(await api.getPerson(personId))
    } catch {
      setResult(null); setError('Persona non trovata o errore nel caricamento.')
    } finally { setLoading(false) }
  }

  return (
    <>
      <div style={formRow}>
        <SearchableSelect fetchOptions={(q) => api.searchEntities('person', q)} placeholder="Cerca per nome…" value={personId} onSelect={setPersonId} />
        <button onClick={run} disabled={loading || !personId} style={{ whiteSpace: 'nowrap' }}>
          {loading ? 'Ricerca…' : 'Cerca'}
        </button>
      </div>

      {error && <div style={errorBox}>{error}</div>}

      {result && (
        <div style={resultBox}>
          <h3 style={{ margin: '0 0 16px', fontSize: 18, color: '#f8fafc' }}>
            {result.personName || result.name || `Persona ${result.id}`}
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <div style={miniCard}><div style={cellLabel}>Nazione</div><div style={cellValue}>{result.country}</div></div>
            <div style={miniCard}><div style={cellLabel}>Genere</div><div style={cellValue}>{result.gender}</div></div>
            <div style={miniCard}>
              <div style={cellLabel}>Data di Nascita</div>
              <div style={cellValue}>
                {result.birthday ? new Date(result.birthday).toLocaleDateString() : 'N/A'}
              </div>
            </div>
            <div style={miniCard}>
              <div style={cellLabel}>Città</div>
              <div style={cellValue}>{result.city_name || result.city || 'N/A'}</div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

/* L2 — Transfer Chain (Neo4j)*/

function PanelL2() {
  const [accountId, setAccountId] = useState('')
  const [hops, setHops] = useState(2)
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (!accountId) return
    setLoading(true); setError('')
    try {
      setResult(await api.getTransferChain(accountId, hops))
    } catch {
      setResult(null); setError('Account non trovato o errore nel calcolo della catena.')
    } finally { setLoading(false) }
  }

  const graphData = useMemo(() => {
    if (!result || !result.nodes) return null
    const nodes = result.nodes.map((id: string) => ({
      id, label: id,
      color: id === accountId ? '#4f46e5' : '#64748b',
    }))
    const edges = result.edges.map((e: any) => ({ from: e.source, to: e.target }))
    return { nodes, edges }
  }, [result, accountId])

  return (
    <>
      <div style={formRow}>
        <SearchableSelect fetchOptions={(q) => api.searchEntities('account', q)} placeholder="Cerca proprietario account…" value={accountId} onSelect={setAccountId} />
        <SliderInput label="Hops" min={1} max={5} value={hops} onChange={setHops} />
        <button onClick={run} disabled={loading || !accountId} style={{ whiteSpace: 'nowrap' }}>
          {loading ? 'Estrazione…' : 'Visualizza'}
        </button>
      </div>

      {error && <div style={errorBox}>{error}</div>}

      {result && graphData && (
        <div style={resultBox}>
          <h3 style={{ fontSize: 16, color: '#f8fafc', marginBottom: 12 }}>Grafo delle transazioni</h3>
          <div style={{ height: 500, borderRadius: 8, border: '1px solid #2a2a3a', overflow: 'hidden', background: '#0d0d1a' }}>
            <GraphViewer data={graphData} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 12, color: '#94a3b8' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#4f46e5', display: 'inline-block' }} /> Partenza
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#64748b', display: 'inline-block' }} /> Standard
            </div>
          </div>
        </div>
      )}
    </>
  )
}

/* L3 — Company Portfolio (Cross-DB)*/

function PanelL3() {
  const [companyId, setCompanyId] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (!companyId) return
    setLoading(true); setError('')
    try {
      setResult(await api.getCompanyPortfolio(companyId))
    } catch {
      setResult(null); setError('Azienda non trovata o nessun conto associato.')
    } finally { setLoading(false) }
  }

  return (
    <>
      <div style={formRow}>
        <SearchableSelect fetchOptions={(q) => api.searchEntities('company', q)} placeholder="Cerca azienda…" value={companyId} onSelect={setCompanyId} />
        <button onClick={run} disabled={loading || !companyId} style={{ whiteSpace: 'nowrap' }}>
          {loading ? 'Ricerca…' : 'Cerca'}
        </button>
      </div>

      {error && <div style={errorBox}>{error}</div>}

      {result && (
        <div style={resultBox}>
          <h3 style={{ fontSize: 16, color: '#f8fafc', marginBottom: 16 }}>
            Conti di proprietà (Totale: {result.total_accounts})
          </h3>
          {result.accounts?.length === 0 ? (
            <p style={{ color: '#64748b' }}>Nessun conto trovato per questa azienda.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 500 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #2a2a3a' }}>
                    <th style={thStyle}>ID Conto</th>
                    <th style={thStyle}>Tipo</th>
                    <th style={thStyle}>Data Apertura</th>
                  </tr>
                </thead>
                <tbody>
                  {result.accounts?.map((acc: any, i: number) => (
                    <tr key={i}>
                      <td style={tdStyle}>{acc.id}</td>
                      <td style={tdStyle}>{acc.type}</td>
                      <td style={tdStyle}>{acc.createTime ? new Date(acc.createTime).toLocaleDateString() : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  )
}

/*A1 — Company Stats / Blocked by Nation (MongoDB)*/

function PanelA1() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function run() {
    setLoading(true)
    try {
      const res = await api.getCompanyStats() as any
      setData(res.analytics || [])
      setDone(true)
    } finally { setLoading(false) }
  }

  return (
    <>
      <div style={{ ...formRow, justifyContent: 'flex-start' }}>
        <button onClick={run} disabled={loading}>
          {loading ? 'Elaborazione…' : 'Esegui analisi'}
        </button>
      </div>

      {done && (
        <div style={resultBox}>
          <h3 style={{ fontSize: 16, color: '#f8fafc', marginBottom: 20 }}>Top 15 Nazioni per Aziende Bloccate</h3>
          <div style={{ height: 360 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.slice(0, 15)} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2a2a3a" />
                <XAxis dataKey="country" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #2a2a3a', background: '#1a1a2e', color: '#e2e8f0' }}
                  itemStyle={{ color: '#e2e8f0' }}
                  cursor={{ fill: '#1e1e2d' }}
                />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: 20, fontSize: 13, color: '#e2e8f0' }} />
                <Bar dataKey="total_companies" name="Totale Aziende" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                <Bar dataKey="blocked_companies" name="Aziende Bloccate" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ marginTop: 24, borderRadius: 8, border: '1px solid #2a2a3a', overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 500 }}>
                <thead>
                  <tr style={{ background: '#13131f', borderBottom: '1px solid #2a2a3a' }}>
                    <th style={thStyle}>Nazione</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Totali</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Bloccate</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>%</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row: any, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid #2a2a3a' }}>
                      <td style={tdStyle}>{row.country || 'Sconosciuta'}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', color: '#94a3b8' }}>{row.total_companies}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', color: '#ef4444', fontWeight: 500 }}>{row.blocked_companies}</td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>
                        <span style={{
                          padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                          background: row.blocked_percentage > 20 ? 'rgba(239,68,68,0.1)'
                            : row.blocked_percentage > 5 ? 'rgba(245,158,11,0.1)' : 'rgba(16,185,129,0.1)',
                          color: row.blocked_percentage > 20 ? '#ef4444'
                            : row.blocked_percentage > 5 ? '#f59e0b' : '#10b981',
                        }}>
                          {row.blocked_percentage ? row.blocked_percentage.toFixed(2) : '0.00'}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

/* A2 — Shortest Path (Neo4j)*/

function PanelA2() {
  const [fromId, setFromId] = useState('')
  const [toId, setToId] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (!fromId || !toId) return
    setLoading(true); setError('')
    try {
      setResult(await api.getShortestPath(fromId, toId))
    } catch {
      setResult(null); setError('Errore nella ricerca del percorso.')
    } finally { setLoading(false) }
  }

  return (
    <>
      <div style={formRow}>
        <SearchableSelect fetchOptions={(q) => api.searchEntities('account', q)} placeholder="Partenza (nome proprietario)…" value={fromId} onSelect={setFromId} />
        <SearchableSelect fetchOptions={(q) => api.searchEntities('account', q)} placeholder="Destinazione (nome proprietario)…" value={toId} onSelect={setToId} />
        <button onClick={run} disabled={loading || !fromId || !toId} style={{ whiteSpace: 'nowrap' }}>
          {loading ? 'Ricerca…' : 'Calcola'}
        </button>
      </div>

      {error && <div style={errorBox}>{error}</div>}

      {result && (
        <div style={resultBox}>
          {!result.path_found ? (
            <p style={{ color: '#f87171', margin: 0 }}>Nessun percorso trovato tra questi due conti.</p>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
                <h3 style={{ margin: 0, fontSize: 18, color: '#10b981' }}>Percorso Trovato!</h3>
                <div style={{
                  fontSize: 14, color: '#94a3b8', background: '#13131f',
                  padding: '6px 12px', borderRadius: 20,
                }}>
                  Hop: <strong style={{ color: '#e2e8f0' }}>{result.jumps}</strong>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                {result.path?.map((id: string, i: number) => (
                  <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{
                      background: '#13131f', padding: '8px 14px', borderRadius: 8, fontSize: 13,
                      border: '1px solid #2a2a3a', fontWeight: 500,
                      color: i === 0 || i === result.path.length - 1 ? '#4f46e5' : '#e2e8f0',
                    }}>
                      {id} {i === 0 ? '(Start)' : i === result.path.length - 1 ? '(End)' : ''}
                    </span>
                    {i < result.path.length - 1 && <span style={{ color: '#4f46e5' }}>→</span>}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </>
  )
}

/* A3 — Laundering Cycle (Cross-DB)*/

function PanelA3() {
  const [accountId, setAccountId] = useState('')
  const [depth, setDepth] = useState(2)
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function run() {
    if (!accountId) return
    setLoading(true)
    try {
      setResult(await api.getLaunderingCycle(accountId, depth))
    } finally { setLoading(false) }
  }

  return (
    <>
      <div style={formRow}>
        <SearchableSelect fetchOptions={(q) => api.searchEntities('account', q)} placeholder="Cerca proprietario account…" value={accountId} onSelect={setAccountId} />
        <SliderInput label="Depth" min={1} max={5} value={depth} onChange={setDepth} />
        <button onClick={run} disabled={loading || !accountId} style={{ whiteSpace: 'nowrap' }}>
          {loading ? 'Elaborazione…' : 'Esegui'}
        </button>
      </div>

      {result && (
        <div style={resultBox}>
          {!result.suspicious_cycle_found ? (
            <p style={{ color: '#94a3b8', margin: 0 }}>Nessun ciclo rilevato per questo account.</p>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
                <h3 style={{ margin: 0, fontSize: 18, color: '#f59e0b' }}>⚠️ Ciclo Rilevato!</h3>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {result.international_laundering && (
                    <span style={{
                      background: 'rgba(239,68,68,0.1)', color: '#ef4444', padding: '6px 12px',
                      borderRadius: 20, fontSize: 13, fontWeight: 600,
                    }}>
                      Rischio Alto (Cross-Border)
                    </span>
                  )}
                </div>
              </div>

              {/* Cycle path */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: 10 }}>Percorso del ciclo</div>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  {result.cycle_path?.map((id: string, i: number) => {
                    const owner = result.owners?.find((o: any) => String(o.id) === String(id))
                    return (
                      <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{
                          background: '#13131f', padding: '8px 14px', borderRadius: 8, fontSize: 13,
                          border: '1px solid #2a2a3a', fontWeight: 500, color: '#e2e8f0',
                        }}>
                          {id} {owner ? `(${owner.name} — ${owner.country})` : ''}
                        </span>
                        {i < result.cycle_path.length - 1 && <span style={{ color: '#4f46e5' }}>→</span>}
                      </span>
                    )
                  })}
                </div>
              </div>

              {/* Owners table */}
              {result.owners && result.owners.length > 0 && (
                <div style={{ borderRadius: 8, border: '1px solid #2a2a3a', overflow: 'hidden' }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 400 }}>
                      <thead>
                        <tr style={{ background: '#13131f', borderBottom: '1px solid #2a2a3a' }}>
                          <th style={thStyle}>Account</th>
                          <th style={thStyle}>Proprietario</th>
                          <th style={thStyle}>Nazione</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.owners.map((o: any, i: number) => (
                          <tr key={i}>
                            <td style={tdStyle}>{o.id}</td>
                            <td style={tdStyle}>{o.name}</td>
                            <td style={tdStyle}>{o.country}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </>
  )
}

/* SLIDER HELPER */

function SliderInput({ label, min, max, value, onChange }: {
  label: string; min: number; max: number; value: number; onChange: (v: number) => void
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, minWidth: 140,
      background: '#13131f', padding: '6px 14px', borderRadius: 8,
      border: '1px solid #2a2a3a',
    }}>
      <span style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap' }}>{label}</span>
      <input
        type="range" min={min} max={max} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{
          flex: 1, accentColor: '#4f46e5', background: 'transparent',
          border: 'none', padding: 0,
        }}
      />
      <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600, minWidth: 16, textAlign: 'center' }}>
        {value}
      </span>
    </div>
  )
}
