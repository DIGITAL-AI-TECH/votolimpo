import { ImageResponse } from "next/og";
import { listEntities, entityToPolitician } from "@/lib/nc-api";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

interface Props {
  params: Promise<{ slug: string }>;
}

function getScoreColor(score: number): string {
  if (score >= 80) return "#10B981";
  if (score >= 60) return "#3B82F6";
  if (score >= 40) return "#EAB308";
  if (score >= 20) return "#F97316";
  return "#EF4444";
}

function getScoreLabel(score: number): string {
  if (score >= 80) return "Excelente";
  if (score >= 60) return "Bom";
  if (score >= 40) return "Regular";
  if (score >= 20) return "Preocupante";
  return "Critico";
}

export default async function OGImage({ params }: Props) {
  const { slug } = await params;

  let name = "Politico";
  let party = "";
  let uf = "";
  let role = "Candidato";
  let score = 50;

  try {
    const firstWord = slug.split("-")[0];
    const entities = await listEntities({
      search: firstWord,
      type: "candidate",
      active: true,
      limit: 100,
    });

    const entity = entities.find((e) => e.slug === slug);
    if (entity) {
      const politician = entityToPolitician(entity);
      name = politician.name;
      party = politician.party;
      uf = politician.uf;
      role = politician.role;
      score = politician.score;
    }
  } catch {
    // fallback values already set
  }

  const scoreColor = getScoreColor(score);
  const scoreLabel = getScoreLabel(score);

  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          display: "flex",
          flexDirection: "column",
          background: "#0A0A0A",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Top accent bar */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background: `linear-gradient(90deg, transparent, ${scoreColor}, transparent)`,
          }}
        />

        {/* Background radial glow */}
        <div
          style={{
            position: "absolute",
            top: -200,
            right: -200,
            width: 700,
            height: 700,
            background: `radial-gradient(ellipse at center, ${scoreColor}10 0%, transparent 70%)`,
          }}
        />

        {/* Main content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            flex: 1,
            padding: "60px 72px",
            justifyContent: "space-between",
          }}
        >
          {/* Header: Voto Limpo branding */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <svg
              width="36"
              height="36"
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
            <span style={{ color: "#6B7280", fontSize: 18, fontWeight: 500 }}>
              Voto Limpo · Transparencia Politica
            </span>
          </div>

          {/* Politician info */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Tags row */}
            <div style={{ display: "flex", gap: 10 }}>
              {party && (
                <div
                  style={{
                    background: "#1A1A1A",
                    border: "1px solid #2E2E2E",
                    borderRadius: 8,
                    padding: "6px 14px",
                    color: "#FAFAFA",
                    fontSize: 16,
                    fontWeight: 600,
                  }}
                >
                  {party}
                </div>
              )}
              {uf && (
                <div
                  style={{
                    background: "#1A1A1A",
                    border: "1px solid #2E2E2E",
                    borderRadius: 8,
                    padding: "6px 14px",
                    color: "#9CA3AF",
                    fontSize: 16,
                  }}
                >
                  {uf}
                </div>
              )}
              <div
                style={{
                  background: "#1A1A1A",
                  border: "1px solid #2E2E2E",
                  borderRadius: 8,
                  padding: "6px 14px",
                  color: "#9CA3AF",
                  fontSize: 16,
                }}
              >
                {role}
              </div>
            </div>

            {/* Name */}
            <div
              style={{
                fontSize: 64,
                fontWeight: 800,
                color: "#FAFAFA",
                letterSpacing: "-2px",
                lineHeight: 1.0,
              }}
            >
              {name}
            </div>
          </div>

          {/* Bottom: score + URL */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "space-between",
            }}
          >
            {/* Score block */}
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 100,
                  height: 100,
                  borderRadius: 16,
                  border: `2px solid ${scoreColor}40`,
                  background: `${scoreColor}15`,
                }}
              >
                <span
                  style={{
                    fontSize: 40,
                    fontWeight: 900,
                    color: scoreColor,
                    lineHeight: 1,
                    fontFamily: "monospace",
                  }}
                >
                  {score}
                </span>
                <span style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}>
                  /100
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: scoreColor,
                  }}
                >
                  {scoreLabel}
                </span>
                <span style={{ fontSize: 14, color: "#6B7280" }}>
                  Indice de Transparencia
                </span>
              </div>
            </div>

            {/* URL */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#10B981",
                }}
              />
              <span style={{ color: "#4B5563", fontSize: 18 }}>
                votolimpo.com.br/politico/{slug}
              </span>
            </div>
          </div>
        </div>

        {/* Bottom border accent */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 3,
            background: `linear-gradient(90deg, transparent, ${scoreColor}, transparent)`,
          }}
        />
      </div>
    ),
    { ...size }
  );
}
