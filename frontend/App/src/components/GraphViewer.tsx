import { useEffect, useRef } from 'react'
import { Network } from 'vis-network'

interface GraphData {
  nodes: { id: string; label: string; color?: string }[]
  edges: { from: string; to: string }[]
}

export default function GraphViewer({ data }: { data: GraphData }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const network = new Network(containerRef.current, data, {
      nodes: { shape: 'dot', size: 16, font: { size: 12 } },
      edges: { arrows: 'to' },
      physics: { stabilization: true }
    })
    return () => network.destroy()
  }, [data])

  return <div ref={containerRef} style={{ height: 400, border: '1px solid #eee', borderRadius: 8 }} />
}
