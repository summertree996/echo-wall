import type { User } from '../types'

const PARTICIPANT_HOME = '/me'
const ADMIN_HOME = '/admin/walls'
const ENTER_PATH = '/enter'

function firstQueryValue(value: unknown): string | null {
  if (Array.isArray(value)) return typeof value[0] === 'string' ? value[0] : null
  return typeof value === 'string' ? value : null
}

export function normalizeNextPath(value: unknown): string | null {
  const raw = firstQueryValue(value)?.trim()
  if (!raw) return null

  let decoded = raw
  try {
    decoded = decodeURIComponent(raw)
  } catch {
    decoded = raw
  }

  if (!decoded.startsWith('/') || decoded.startsWith('//')) return null
  if (decoded === ENTER_PATH || decoded.startsWith(`${ENTER_PATH}?`)) return null
  return decoded
}

export function resolveAfterLogin(user: User, nextValue?: unknown): string {
  const next = normalizeNextPath(nextValue)

  if (next) {
    if (next.startsWith('/admin') && !user.is_admin) return PARTICIPANT_HOME
    return next
  }

  return user.is_admin ? ADMIN_HOME : PARTICIPANT_HOME
}

export function loginPathFor(next?: string | null): string {
  const safeNext = normalizeNextPath(next)
  if (!safeNext) return ENTER_PATH
  return `${ENTER_PATH}?next=${encodeURIComponent(safeNext)}`
}
