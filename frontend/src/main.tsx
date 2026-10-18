import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/base.css'
import './components/ui/ui.css'
import './features/planner/planner.css'
import './features/routes/routes.css'
import './layout.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
