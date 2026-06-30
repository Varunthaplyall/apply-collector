import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './lib/AuthContext'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
import { ToastProvider } from './lib/ToastContext'
import NavHeader from './components/NavHeader'
import ProtectedRoute from './components/ProtectedRoute'
import PageTransition from './components/PageTransition'
import ErrorBoundary from './components/ErrorBoundary'
import MainPage from './pages/MainPage'
import LoginPage from './pages/LoginPage'

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route
          path="/login"
          element={
            <PageTransition>
              <LoginPage />
            </PageTransition>
          }
        />

        {/* All protected pages → single MainPage */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <PageTransition>
                <MainPage />
              </PageTransition>
            </ProtectedRoute>
          }
        />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <QueryClientProvider client={queryClient}>
            <ErrorBoundary>
              <div className="h-screen flex flex-col bg-background bg-grid overflow-hidden">
                <a href="#main-content" className="skip-to-content">Skip to content</a>
                <NavHeader />
                <div className="flex-1 min-h-0" id="main-content">
                  <AnimatedRoutes />
                </div>
              </div>
            </ErrorBoundary>
          </QueryClientProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
