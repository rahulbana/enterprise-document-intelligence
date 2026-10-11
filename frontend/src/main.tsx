// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import 'bootswatch/dist/materia/bootstrap.min.css'

import { App } from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
