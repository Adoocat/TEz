// Glue between openapi-fetch results and TanStack Query: failed requests throw an ApiError
// carrying the backend's error code, which the UI translates (errors.<code>).
import { isApiError } from "./client";

export class ApiError extends Error {
  readonly code: string;
  readonly params: Record<string, unknown>;
  readonly status: number;

  constructor(code: string, params: Record<string, unknown>, status: number) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.params = params;
    this.status = status;
  }
}

interface Result<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** The response data, or an ApiError with the backend's code. */
export function unwrap<T>({ data, error, response }: Result<T>): T {
  if (error !== undefined || !response.ok) {
    if (isApiError(error))
      throw new ApiError(error.error.code, error.error.params ?? {}, response.status);
    throw new ApiError("http.error", { status: response.status }, response.status);
  }
  return data as T;
}

/** For endpoints without a body (204). */
export function unwrapEmpty({ error, response }: Result<unknown>): void {
  unwrap({ data: undefined, error, response });
}
