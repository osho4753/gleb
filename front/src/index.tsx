import './index.css'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { CashDeskProvider } from './services/cashDeskService'

const container = document.getElementById('root')
const root = createRoot(container!)
root.render(
  <CashDeskProvider>
    <App />
  </CashDeskProvider>
)
