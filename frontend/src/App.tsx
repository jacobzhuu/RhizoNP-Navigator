import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AskPage } from './pages/Ask'
import { EvidenceGraderPage } from './pages/EvidenceGrader'
import { GroundedReportPage } from './pages/GroundedReport'
import { LimitationsPage } from './pages/Limitations'
import { LiteratureExplorerPage } from './pages/LiteratureExplorer'
import { NaturalProductsPage } from './pages/NaturalProducts'
import { NotFoundPage } from './pages/NotFound'
import { OwnDataPage } from './pages/OwnData'
import { OverviewPage } from './pages/Overview'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<AskPage />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="literature" element={<LiteratureExplorerPage />} />
          <Route path="evidence-grader" element={<EvidenceGraderPage />} />
          <Route path="natural-products" element={<NaturalProductsPage />} />
          <Route path="own-data" element={<OwnDataPage />} />
          <Route path="grounded-report" element={<GroundedReportPage />} />
          <Route path="about/limitations" element={<LimitationsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
