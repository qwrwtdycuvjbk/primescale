/**
 * Centralized Django REST Framework API Client for Next.js.
 * Handles base URL configuration, headers, JSON and multipart requests,
 * and standard error parsing.
 */

export const DJANGO_API_BASE_URL =
  process.env.NEXT_PUBLIC_DJANGO_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export type RequestOptions = RequestInit & {
  params?: Record<string, string | number | boolean | undefined>;
  token?: string;
};

/**
 * Builds full URL with optional query parameters.
 */
function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): string {
  const base = DJANGO_API_BASE_URL.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${base}${cleanPath}`);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  return url.toString();
}

/**
 * Executes an HTTP request against the Django backend.
 */
export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { params, token, headers, ...customConfig } = options;

  const url = buildUrl(path, params);

  const defaultHeaders: Record<string, string> = {
    Accept: "application/json",
  };

  if (!(customConfig.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  if (token) {
    defaultHeaders["Authorization"] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    credentials: "include",
    ...customConfig,
    headers: {
      ...defaultHeaders,
      ...(headers as Record<string, string>),
    },
  };

  const response = await fetch(url, config);

  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get("content-type");
  const isJson = contentType && contentType.includes("application/json");
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null && "error" in data
        ? String((data as { error: unknown }).error)
        : typeof data === "object" && data !== null && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : `Request failed with status ${response.status}`;

    throw new ApiError(response.status, message, data);
  }

  return data as T;
}

export const djangoApi = {
  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return apiRequest<T>(path, { ...options, method: "GET" });
  },

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return apiRequest<T>(path, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  },

  patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return apiRequest<T>(path, {
      ...options,
      method: "PATCH",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  },

  delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return apiRequest<T>(path, { ...options, method: "DELETE" });
  },
};
