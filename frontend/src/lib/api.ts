export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

export interface ProfileMetrics {
  height?: number;
  weight?: number;
  age: number;
  fitness_score?: number;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: "athlete" | "coach" | "organizer" | "referee";
  profile_metrics: ProfileMetrics;
  device_token?: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface VaultDocument {
  id: string;
  user_id: string;
  user_name?: string;
  user_email?: string;
  doc_type: "ID" | "MEDICAL" | "WAIVER" | string;
  storage_url: string;
  is_verified: boolean;
  uploaded_at: string;
}

export interface SportEvent {
  id: string;
  sport_name: string;
  title: string;
  venue: string;
  organizer_id: string;
  date_time: string;
  entry_fee: number;
  capacity: number;
  mandatory_requirements: string[];
  registered_count: number;
  eligible?: boolean | null;
}

export interface EligibilityCheckItem {
  requirement: string;
  passed: boolean;
  message: string;
}

export interface EligibilityResponse {
  eligible: boolean;
  checks: EligibilityCheckItem[];
}

export interface RegistrationItem {
  id: string;
  event_id: string;
  user_id: string;
  status: "PENDING_PAYMENT" | "CONFIRMED" | "CANCELLED";
  payment_id?: string | null;
}

export interface Court {
  id: string;
  name: string;
  sport_name: string;
  venue: string;
  hourly_price: number;
}

export interface SlotAvailability {
  slot_start: string;
  slot_end: string;
  label: string;
  available: boolean;
  status: "AVAILABLE" | "LOCKED" | "BOOKED";
}

export interface BookingItem {
  id: string;
  user_id: string;
  court_id: string;
  court_name?: string;
  venue?: string;
  hourly_price?: number;
  slot_start: string;
  slot_end: string;
  payment_status: "PENDING" | "CONFIRMED" | "FAILED";
  created_at: string;
}

export interface PaymentIntentResponse {
  payment_id: string;
  gateway: string;
  order_id: string;
  amount: number;
  currency: string;
  mode: string;
  checkout_url_or_token: string;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  title: string;
  body: string;
  kind: string;
  sent_at: string;
  read: boolean;
}

export interface ScheduledMatchItem {
  match_index: number;
  team_a: string;
  team_b: string;
  court_number: number;
  slot_index: number;
  start_time: string;
  end_time: string;
}

export interface SchedulerGenerateResponse {
  format: string;
  total_matches: number;
  makespan_slots: number;
  solver_status: string;
  timetable: ScheduledMatchItem[];
}

export interface LiveMatch {
  id: string;
  tournament_id: string;
  event_title?: string;
  sport_name?: string;
  team_a: string;
  team_b: string;
  court_number: number;
  start_time: string;
  score_a: number;
  score_b: number;
  status: "SCHEDULED" | "LIVE" | "FINISHED";
}

export class ApiError extends Error {
  status: number;
  checks?: EligibilityCheckItem[];

  constructor(message: string, status: number, checks?: EligibilityCheckItem[]) {
    super(message);
    this.status = status;
    this.checks = checks;
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sportshub_jwt");
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    let checks: EligibilityCheckItem[] | undefined = undefined;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") {
        errMsg = data.detail;
      } else if (data.detail && typeof data.detail === "object") {
        errMsg = data.detail.message || JSON.stringify(data.detail);
        if (Array.isArray(data.detail.checks)) {
          checks = data.detail.checks;
        }
      }
    } catch {
      // ignore json parse failure
    }
    throw new ApiError(errMsg, res.status, checks);
  }

  return res.json() as Promise<T>;
}

export function formatINR(paise: number): string {
  if (!paise || paise <= 0) return "Free";
  return `₹${(paise / 100).toFixed(0)}`;
}

