import { describe, it, expect } from 'vitest'
import { cn, formatNumber, formatPercent, safeUrl, timeAgo } from '../lib/utils'

describe('cn (className merge)', () => {
  it('merges class strings', () => {
    expect(cn('px-4', 'py-2')).toBe('px-4 py-2')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'extra')).toBe('base extra')
  })

  it('handles undefined and null', () => {
    expect(cn('base', undefined, null, 'extra')).toBe('base extra')
  })

  it('returns empty string for no inputs', () => {
    expect(cn()).toBe('')
  })
})

describe('formatNumber', () => {
  it('formats millions', () => {
    expect(formatNumber(1_500_000)).toBe('1.5M')
  })

  it('formats thousands', () => {
    expect(formatNumber(5_400)).toBe('5.4K')
  })

  it('formats small numbers with locale', () => {
    expect(formatNumber(42)).toBe('42')
  })

  it('handles zero', () => {
    expect(formatNumber(0)).toBe('0')
  })
})

describe('formatPercent', () => {
  it('calculates percentage correctly', () => {
    expect(formatPercent(25, 100)).toBe('25.0%')
  })

  it('returns 0% when total is zero', () => {
    expect(formatPercent(5, 0)).toBe('0%')
  })

  it('rounds to one decimal', () => {
    expect(formatPercent(1, 3)).toBe('33.3%')
  })
})

describe('safeUrl', () => {
  it('passes through https URLs', () => {
    expect(safeUrl('https://example.com')).toBe('https://example.com')
  })

  it('passes through http URLs', () => {
    expect(safeUrl('http://example.com')).toBe('http://example.com')
  })

  it('blocks javascript: URLs', () => {
    expect(safeUrl('javascript:alert(1)')).toBe('#')
  })

  it('blocks data: URLs', () => {
    expect(safeUrl('data:text/html,<script>alert(1)</script>')).toBe('#')
  })

  it('blocks relative paths', () => {
    expect(safeUrl('/api/internal')).toBe('#')
  })
})

describe('timeAgo', () => {
  it('returns "just now" for recent timestamps', () => {
    const now = new Date()
    expect(timeAgo(now.toISOString())).toBe('just now')
  })

  it('returns minutes ago', () => {
    const date = new Date(Date.now() - 5 * 60 * 1000)
    expect(timeAgo(date.toISOString())).toBe('5m ago')
  })

  it('returns hours ago', () => {
    const date = new Date(Date.now() - 3 * 60 * 60 * 1000)
    expect(timeAgo(date.toISOString())).toBe('3h ago')
  })

  it('returns days ago', () => {
    const date = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000)
    expect(timeAgo(date.toISOString())).toBe('2d ago')
  })

  it('returns date string for older dates', () => {
    const date = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    const result = timeAgo(date.toISOString())
    // Should be a date string like "Jun 1" not a relative time
    expect(result).toMatch(/^[A-Z][a-z]{2} \d{1,2}$/)
  })
})
