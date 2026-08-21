import type { ApiProblem } from "~/types/api";

export class ApiError extends Error {
  constructor(message: string, public readonly status = 0, public readonly data?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiErrorMessage(data: unknown, fallback = "Não foi possível concluir a operação."): string {
  if (!data || typeof data !== "object") return fallback;
  const problem = data as ApiProblem;
  if (typeof problem.detail === "string") return problem.detail;
  if (Array.isArray(problem.detail)) {
    const messages = problem.detail.map((item) => item.msg).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return problem.message || problem.error || fallback;
}
