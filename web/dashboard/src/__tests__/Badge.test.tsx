import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '../components/ui/Badge'

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Active</Badge>)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('applies default color by default', () => {
    render(<Badge>Default</Badge>)
    const el = screen.getByText('Default')
    expect(el.className).toContain('bg-muted')
  })

  it('applies success color', () => {
    render(<Badge color="success">Success</Badge>)
    const el = screen.getByText('Success')
    expect(el.className).toContain('text-emerald-400')
  })

  it('applies warning color', () => {
    render(<Badge color="warning">Warning</Badge>)
    const el = screen.getByText('Warning')
    expect(el.className).toContain('text-amber-400')
  })

  it('applies danger color', () => {
    render(<Badge color="danger">Danger</Badge>)
    const el = screen.getByText('Danger')
    expect(el.className).toContain('text-red-400')
  })

  it('applies info color', () => {
    render(<Badge color="info">Info</Badge>)
    const el = screen.getByText('Info')
    expect(el.className).toContain('text-blue-400')
  })

  it('applies violet color', () => {
    render(<Badge color="violet">Violet</Badge>)
    const el = screen.getByText('Violet')
    expect(el.className).toContain('text-violet-400')
  })

  it('applies sm size', () => {
    render(<Badge size="sm">Small</Badge>)
    const el = screen.getByText('Small')
    expect(el.className).toContain('text-[10px]')
  })

  it('applies md size by default', () => {
    render(<Badge>Medium</Badge>)
    const el = screen.getByText('Medium')
    expect(el.className).toContain('text-xs')
  })

  it('passes additional className', () => {
    render(<Badge className="ml-2">Extra</Badge>)
    const el = screen.getByText('Extra')
    expect(el.className).toContain('ml-2')
  })

  it('renders as a span element', () => {
    render(<Badge>Span</Badge>)
    const el = screen.getByText('Span')
    expect(el.tagName).toBe('SPAN')
  })
})
