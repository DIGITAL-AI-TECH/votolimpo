import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Voto Limpo — Transparencia Politica Brasileira";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#0A0A0A",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Background gradient radial */}
        <div
          style={{
            position: "absolute",
            top: -100,
            left: "50%",
            transform: "translateX(-50%)",
            width: 800,
            height: 600,
            background:
              "radial-gradient(ellipse at center top, rgba(16,185,129,0.12) 0%, transparent 70%)",
          }}
        />

        {/* Logo / Icon */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 32,
          }}
        >
          <svg
            width="72"
            height="72"
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M32 4 L56 14 L56 34 C56 47 45 57 32 60 C19 57 8 47 8 34 L8 14 Z"
              fill="#10B981"
            />
            <path
              d="M20 32 L28 40 L44 22"
              stroke="white"
              strokeWidth="5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Title */}
        <div
          style={{
            fontSize: 60,
            fontWeight: 800,
            color: "#FAFAFA",
            letterSpacing: "-1px",
            textAlign: "center",
            lineHeight: 1.1,
            marginBottom: 20,
          }}
        >
          Voto{" "}
          <span style={{ color: "#10B981" }}>Limpo</span>
        </div>

        {/* Tagline */}
        <div
          style={{
            fontSize: 26,
            color: "#6B7280",
            textAlign: "center",
            maxWidth: 700,
            lineHeight: 1.4,
            marginBottom: 40,
          }}
        >
          Transparencia politica ao alcance de todos
        </div>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: 48,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {[
            { label: "Politicos monitorados", icon: "👤" },
            { label: "Artigos indexados", icon: "📰" },
            { label: "Fontes de noticias", icon: "🔗" },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ fontSize: 28 }}>{item.icon}</span>
              <span
                style={{
                  fontSize: 13,
                  color: "#6B7280",
                  textAlign: "center",
                }}
              >
                {item.label}
              </span>
            </div>
          ))}
        </div>

        {/* Bottom URL */}
        <div
          style={{
            position: "absolute",
            bottom: 32,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#10B981",
            }}
          />
          <span style={{ color: "#4B5563", fontSize: 18 }}>
            votolimpo.com.br
          </span>
        </div>

        {/* Border bottom accent */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 4,
            background: "linear-gradient(90deg, transparent, #10B981, transparent)",
          }}
        />
      </div>
    ),
    { ...size }
  );
}
