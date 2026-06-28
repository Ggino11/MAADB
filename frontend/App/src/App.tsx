import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Home from './pages/Home'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', height: '100vh', fontFamily: 'Inter, sans-serif' }}>
        <Sidebar />
        <main style={{ flex: 1, overflowY: 'auto', backgroundColor: '#0d0d1a' }}>
          <Routes>
            <Route path="*" element={<Home />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
