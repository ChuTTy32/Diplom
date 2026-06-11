export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  async function get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const url = new URL(base + path)
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
    }
    const res = await fetch(url.toString())
    if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
    return res.json()
  }

  return { get }
}

export function usePolling(fn: () => Promise<void>, intervalMs = 5000) {
  let timer: ReturnType<typeof setInterval> | null = null
  onMounted(async () => {
    await fn()
    timer = setInterval(fn, intervalMs)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })
}
