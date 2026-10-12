import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
const App = import.meta.env.MODE === 'workspace'
  ? lazy(() => import('./App.tsx'))
  : lazy(() => import('./DemoApp.tsx'))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={<div style={{ padding: 32 }}>図面とチェック結果を読み込み中…</div>}><App /></Suspense>
  </StrictMode>,
)
