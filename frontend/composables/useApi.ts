import { ApiError, apiErrorMessage } from "~/services/api/error";

function normalizedBaseUrl(value: string): string {
  const base = value.replace(/\/$/, "");
  return /\/api\/v\d+$/.test(base) ? base : `${base}/api/v1`;
}

export function useApi() {
  const config = useRuntimeConfig();
  const auth = useAuthStore();

  async function request<T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}): Promise<T> {
    try {
      return await $fetch<T>(path, {
        ...options,
        baseURL: normalizedBaseUrl(config.public.apiBaseUrl),
        headers: {
          ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
          ...((options.headers as Record<string, string> | undefined) ?? {}),
        },
      });
    } catch (error: unknown) {
      const response = (error as { response?: { status?: number; _data?: unknown } }).response;
      throw new ApiError(apiErrorMessage(response?._data), response?.status ?? 0, response?._data);
    }
  }

  return {
    get: <T>(path: string, query?: Record<string, unknown>) => request<T>(path, { method: "GET", query }),
    post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body as never }),
    put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body as never }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body as never }),
    delete: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
      request<T>(path, { method: "DELETE", body: body as never, query }),
    request,
  };
}
