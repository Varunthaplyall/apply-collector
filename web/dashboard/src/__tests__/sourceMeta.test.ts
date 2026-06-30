import { describe, it, expect } from 'vitest'
import {
  SOURCE_META,
  SOURCE_LIST,
  ACTIVE_PIPELINE_SOURCES,
  getSourceMeta,
  type SourceMeta,
} from '../lib/sourceMeta'

describe('SOURCE_META', () => {
  it('has entries for all active pipeline sources', () => {
    for (const source of ACTIVE_PIPELINE_SOURCES) {
      expect(SOURCE_META[source]).toBeDefined()
    }
  })

  it('every entry has required fields', () => {
    for (const [key, meta] of Object.entries(SOURCE_META)) {
      expect(meta.name).toBe(key)
      expect(meta.label).toBeTruthy()
      expect(meta.color).toBeTruthy()
      expect(meta.gradient).toMatch(/^from-\w+-\d+ to-\w+-\d+$/)
    }
  })

  it('contains all 14 known sources', () => {
    expect(Object.keys(SOURCE_META)).toHaveLength(14)
  })
})

describe('SOURCE_LIST', () => {
  it('matches SOURCE_META values', () => {
    expect(SOURCE_LIST).toHaveLength(14)
    for (const meta of SOURCE_LIST) {
      expect(SOURCE_META[meta.name]).toBe(meta)
    }
  })
})

describe('ACTIVE_PIPELINE_SOURCES', () => {
  it('contains expected active sources', () => {
    expect(ACTIVE_PIPELINE_SOURCES).toContain('greenhouse')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('lever')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('remotive')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('remoteok')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('arbeitnow')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('himalayas')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('yc_jobs')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('cutshort')
    expect(ACTIVE_PIPELINE_SOURCES).toContain('linkedin')
  })

  it('has no duplicates', () => {
    expect(new Set(ACTIVE_PIPELINE_SOURCES).size).toBe(ACTIVE_PIPELINE_SOURCES.length)
  })
})

describe('getSourceMeta', () => {
  it('returns metadata for known sources', () => {
    const meta = getSourceMeta('greenhouse')
    expect(meta.label).toBe('Greenhouse')
    expect(meta.color).toBe('emerald')
  })

  it('returns fallback for unknown sources', () => {
    const meta = getSourceMeta('unknown-source')
    expect(meta.name).toBe('unknown-source')
    expect(meta.label).toBe('Unknown-source')
    expect(meta.color).toBe('gray')
    expect(meta.gradient).toBe('from-gray-400 to-gray-500')
  })
})
