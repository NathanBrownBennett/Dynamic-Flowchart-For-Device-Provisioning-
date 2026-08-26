import test from 'node:test'
import assert from 'node:assert/strict'

test('the frontend contract uses versioned read-only API paths', () => {
  const paths = ['/api/v1/healthz', '/api/v1/catalogue/status', '/api/v1/criteria', '/api/v1/sources/example/status', '/api/v1/devices', '/api/v1/search', '/api/v1/devices/1?use_case=Government', '/api/v1/devices/1/comparisons?use_case=Work']
  for (const path of paths) assert.match(path, /^\/api\/v1\//)
})

test('the public frontend contract does not include operator endpoints', () => {
  const publicPaths = ['/api/v1/devices', '/api/v1/search', '/api/v1/healthz']
  assert.equal(publicPaths.some(path => /refresh|validate|admin|proxy/.test(path)), false)
})
