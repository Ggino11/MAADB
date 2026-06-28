import { useState, useEffect, useRef } from 'react'

export interface Suggestion {
  id: string
  label: string
}

interface Props {
  fetchOptions: (q: string) => Promise<Suggestion[]>
  placeholder: string
  onSelect: (id: string) => void
  value: string
}

export default function SearchableSelect({ fetchOptions, placeholder, onSelect, value }: Props) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState<Suggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null)
  
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (!open) return
    
    // Debounce fetch
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    
    if (search.length < 2) {
      setOptions([])
      return
    }

    timeoutRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetchOptions(search)
        setOptions(res || [])
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }, 300)

  }, [search, open, fetchOptions])

  const handleSelect = (s: Suggestion) => {
    setSelectedLabel(s.label)
    onSelect(s.id)
    setSearch('')
    setOpen(false)
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
      <input
        value={value && !open ? (selectedLabel || '') : search}
        onChange={(e) => { setSearch(e.target.value); setOpen(true); onSelect('') }}
        onFocus={() => { setOpen(true); setSearch('') }}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder={value && !open && selectedLabel ? selectedLabel : placeholder}
        style={{
          width: '100%', padding: '10px 14px', borderRadius: 8,
          border: '1px solid #2a2a3a', background: '#13131f',
          color: '#e2e8f0', fontSize: 14, outline: 'none',
        }}
      />
      {open && search.length >= 2 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          minWidth: 300,
          background: '#1a1a2e', border: '1px solid #2a2a3a', borderRadius: 8,
          maxHeight: 300, overflowY: 'auto', marginTop: 4,
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        }}>
          {loading && (
            <div style={{ padding: '10px 14px', color: '#64748b', fontSize: 13 }}>Caricamento...</div>
          )}
          {!loading && options.length === 0 && (
            <div style={{ padding: '10px 14px', color: '#64748b', fontSize: 13 }}>Nessun risultato</div>
          )}
          {!loading && options.map((o) => (
            <div
              key={o.id}
              onMouseDown={() => handleSelect(o)}
              style={{
                padding: '10px 14px', cursor: 'pointer',
                borderBottom: '1px solid #1e1e30',
                transition: 'background 0.1s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#252540')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{
                fontSize: 14, color: '#e2e8f0', whiteSpace: 'nowrap',
                overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {o.label || o.id}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
