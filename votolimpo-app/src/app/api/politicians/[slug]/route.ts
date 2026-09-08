import { NextResponse } from "next/server";
import {
  getPoliticianBySlug,
  getArticlesForPolitician,
  getMilestonesForPolitician,
  getRelationshipsForPolitician,
} from "@/lib/mock-data";

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export async function GET(_request: Request, { params }: RouteParams) {
  const { slug } = await params;
  const politician = getPoliticianBySlug(slug);

  if (!politician) {
    return NextResponse.json({ error: "Politician not found" }, { status: 404 });
  }

  const articles = getArticlesForPolitician(politician.id);
  const milestones = getMilestonesForPolitician(politician.id);
  const relationships = getRelationshipsForPolitician(politician.id);

  return NextResponse.json({
    politician,
    articles,
    milestones,
    relationships,
  });
}
