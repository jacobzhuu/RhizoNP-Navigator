import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AskSessionProvider } from './context/AskSessionContext'
import { ResultsSessionProvider } from './context/ResultsSessionContext'
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
import { ResultsPage } from './pages/Results'
import { HistoryPage } from './pages/History'

export default function App() {
  return (
    <BrowserRouter>
      <AskSessionProvider>
        <ResultsSessionProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<OverviewPage />} />
              <Route path="ask" element={<AskPage />} />
              <Route path="results" element={<ResultsPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="history/:historyId" element={<HistoryPage />} />
              <Route path="about" element={<LimitationsPage />} />
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
        </ResultsSessionProvider>
      </AskSessionProvider>
    </BrowserRouter>
  )
}
