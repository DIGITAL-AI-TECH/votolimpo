import { NextResponse } from "next/server";
import { getGraphData } from "@/lib/mock-data";

export async function GET() {
  const graphData = getGraphData();
  return NextResponse.json(graphData);
}
