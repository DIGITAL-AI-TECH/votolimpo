import { cookies } from "next/headers";
import { createHmac, timingSafeEqual } from "crypto";

const SECRET = process.env.HELPCORE_AUTH_SECRET || (process.env.NODE_ENV === "production" ? (() => { throw new Error("HELPCORE_AUTH_SECRET must be set in production"); })() : "dev-secret-change-me");
const COOKIE_NAME = "hc_session";
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export function generateToken(): string {
  const timestamp = Date.now().toString();
  const signature = createHmac("sha256", SECRET)
    .update(timestamp)
    .digest("hex");
  return `${timestamp}.${signature}`;
}

export function validateToken(token: string): boolean {
  const parts = token.split(".");
  if (parts.length !== 2) return false;

  const [timestamp, signature] = parts;
  const expectedSignature = createHmac("sha256", SECRET)
    .update(timestamp)
    .digest("hex");

  if (
    signature.length !== expectedSignature.length ||
    !timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSignature))
  ) return false;

  const tokenAge = Date.now() - parseInt(timestamp, 10);
  return tokenAge < MAX_AGE * 1000;
}

export async function setSessionCookie(): Promise<void> {
  const token = generateToken();
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    maxAge: MAX_AGE,
    path: "/",
  });
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

export async function getSessionToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(COOKIE_NAME)?.value;
}

export async function isAuthenticated(): Promise<boolean> {
  const token = await getSessionToken();
  if (!token) return false;
  return validateToken(token);
}
