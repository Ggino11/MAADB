import { NavLink } from 'react-router-dom'

export default function Sidebar() {
  return (
    <nav style={{
      width: 240, borderRight: '1px solid #2a2a3a', padding: '24px 0',
      backgroundColor: '#0d0d1a', boxShadow: '2px 0 20px rgba(0,0,0,0.5)', zIndex: 10,
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Logo */}
      <div style={{
        padding: '0 24px 32px', fontWeight: 800, fontSize: 22, color: '#f8fafc',
        letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'linear-gradient(135deg, #4f46e5 0%, #8b5cf6 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 16,
        }}>
          ✧
        </div>
        MAADB
      </div>

      {/* Single link */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '0 12px' }}>
        <NavLink
          to="/"
          style={({ isActive }) => ({
            display: 'flex', alignItems: 'center',
            padding: '12px 16px', textDecoration: 'none', fontSize: 14, fontWeight: 500,
            color: isActive ? '#f8fafc' : '#94a3b8',
            background: isActive ? '#1a1a2e' : 'transparent',
            borderRadius: 8,
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            borderLeft: isActive ? '4px solid #4f46e5' : '4px solid transparent',
          })}
        >
          Home
        </NavLink>
      </div>
    </nav>
  )
}
