import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 180,
          height: 180,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0A0A0A",
          borderRadius: 36,
        }}
      >
        <svg
          width="140"
          height="140"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Urna body */}
          <rect x="8" y="16" width="48" height="40" rx="4" fill="#1A1A1A" stroke="#10B981" strokeWidth="2" />
          {/* Screen */}
          <rect x="14" y="22" width="24" height="16" rx="2" fill="#0A0A0A" stroke="#10B981" strokeWidth="1" />
          {/* Checkmark on screen */}
          <path d="M20 30 L25 35 L34 25" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          {/* Keypad */}
          <rect x="42" y="22" width="4" height="4" rx="1" fill="#6B7280" />
          <rect x="48" y="22" width="4" height="4" rx="1" fill="#6B7280" />
          <rect x="42" y="28" width="4" height="4" rx="1" fill="#6B7280" />
          <rect x="48" y="28" width="4" height="4" rx="1" fill="#6B7280" />
          <rect x="42" y="34" width="4" height="4" rx="1" fill="#FAFAFA" />
          <rect x="48" y="34" width="10" height="4" rx="1" fill="#10B981" />
          {/* Slot */}
          <rect x="20" y="44" width="24" height="4" rx="2" fill="#2E2E2E" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
