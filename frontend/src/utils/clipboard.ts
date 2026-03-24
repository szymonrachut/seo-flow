export async function copyText(value: string): Promise<boolean> {
  const clipboard = globalThis.navigator?.clipboard
  if (!clipboard || typeof clipboard.writeText !== 'function') {
    return false
  }

  await clipboard.writeText(value)
  return true
}
