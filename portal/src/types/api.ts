export type ResponseStatus = "success" | "error";

export interface ApiResponse<T = unknown> {
  ok: boolean;
  status: ResponseStatus;
  message: string | null;
  data: T | null;
}

export function isOk<T>(
  response: ApiResponse<T> | null | undefined,
): response is ApiResponse<T> & { ok: true; data: T } {
  return !!response?.ok;
}

export interface SignupContext {
  is_open: boolean;
  app_title: string | null;
  logo: string | null;
  contact_email: string | null;
  closed_message: string | null;
  party_types: string[];
}

export interface SignupResult {
  email: string;
  email_sent: boolean;
}
