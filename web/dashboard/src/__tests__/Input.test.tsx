import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Input } from '../components/ui/Input'

describe('Input', () => {
  it('renders a text input by default', () => {
    render(<Input aria-label="Test input" />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders with a label', () => {
    render(<Input label="Email" />)
    expect(screen.getByText('Email')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveAttribute('id', 'email')
  })

  it('renders with a hint', () => {
    render(<Input label="Name" hint="Full legal name" />)
    expect(screen.getByText('Full legal name')).toBeInTheDocument()
  })

  it('renders error message', () => {
    render(<Input label="Email" error="Invalid email" />)
    expect(screen.getByText('Invalid email')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true')
  })

  it('does not show hint when error is present', () => {
    render(<Input label="Email" hint="Enter email" error="Required" />)
    expect(screen.queryByText('Enter email')).not.toBeInTheDocument()
    expect(screen.getByText('Required')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<Input className="w-full" aria-label="test" />)
    expect(screen.getByRole('textbox').className).toContain('w-full')
  })

  it('passes through native input attributes', () => {
    render(<Input placeholder="Search..." aria-label="search" />)
    expect(screen.getByRole('textbox')).toHaveAttribute('placeholder', 'Search...')
  })

  it('supports disabled state', () => {
    render(<Input disabled aria-label="disabled input" />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})
