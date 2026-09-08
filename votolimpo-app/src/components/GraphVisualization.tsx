"use client";

import { useEffect, useRef, useState, type FC } from "react";
import { useRouter } from "next/navigation";
import type { GraphData } from "@/types";

interface GraphVisualizationProps {
  data: GraphData;
}

const REL_COLORS: Record<string, string> = {
  donation: "#EF4444",
  contract: "#F97316",
  board_member: "#EAB308",
  investigation: "#EF4444",
  business_partner: "#3B82F6",
  family: "#A855F7",
};

const GraphVisualization: FC<GraphVisualizationProps> = ({ data }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string } | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !svgRef.current || !containerRef.current) return;

    const loadD3 = async () => {
      const d3 = await import("d3");

      const container = containerRef.current!;
      const svg = d3.select(svgRef.current!);
      svg.selectAll("*").remove();

      const width = container.clientWidth || 800;
      const height = container.clientHeight || 600;

      svg
        .attr("width", width)
        .attr("height", height)
        .attr("viewBox", `0 0 ${width} ${height}`);

      const g = svg.append("g");

      // Zoom behavior
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on("zoom", (event) => {
          g.attr("transform", event.transform);
        });

      svg.call(zoom);

      // Clone nodes and edges for D3 simulation
      type SimNode = d3.SimulationNodeDatum & {
        id: string;
        type: "politician" | "entity";
        label: string;
        slug?: string;
        party?: string;
        partyColor?: string;
        score?: number;
        entityType?: string;
      };
      const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }));
      const edges = data.edges.map((e) => ({ ...e }));

      // Simulation
      const simulation = d3
        .forceSimulation<SimNode>(nodes)
        .force(
          "link",
          d3
            .forceLink(edges)
            .id((d: d3.SimulationNodeDatum) => (d as { id: string }).id)
            .distance(120)
        )
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide(40));

      // Arrow markers
      const defs = svg.append("defs");
      Object.entries(REL_COLORS).forEach(([type, color]) => {
        defs
          .append("marker")
          .attr("id", `arrow-${type}`)
          .attr("viewBox", "0 -5 10 10")
          .attr("refX", 20)
          .attr("refY", 0)
          .attr("markerWidth", 6)
          .attr("markerHeight", 6)
          .attr("orient", "auto")
          .append("path")
          .attr("d", "M0,-5L10,0L0,5")
          .attr("fill", color)
          .attr("opacity", 0.6);
      });

      // Links
      const link = g
        .append("g")
        .selectAll("line")
        .data(edges)
        .enter()
        .append("line")
        .attr("stroke", (d) => REL_COLORS[d.type] || "#6B7280")
        .attr("stroke-opacity", 0.4)
        .attr("stroke-width", 1.5)
        .attr("marker-end", (d) => `url(#arrow-${d.type})`);

      // Node groups
      const node = g
        .append("g")
        .selectAll("g")
        .data(nodes)
        .enter()
        .append("g")
        .attr("cursor", "pointer")
        .call(
          d3
            .drag<SVGGElement, SimNode>()
            .on("start", (event, d) => {
              if (!event.active) simulation.alphaTarget(0.3).restart();
              d.fx = d.x;
              d.fy = d.y;
            })
            .on("drag", (event, d) => {
              d.fx = event.x;
              d.fy = event.y;
            })
            .on("end", (event, d) => {
              if (!event.active) simulation.alphaTarget(0);
              d.fx = null;
              d.fy = null;
            })
        );

      // Politician nodes (circles)
      node
        .filter((d) => d.type === "politician")
        .append("circle")
        .attr("r", 20)
        .attr("fill", (d) => (d.partyColor || "#10B981") + "33")
        .attr("stroke", (d) => {
          const score = d.score || 50;
          if (score >= 80) return "#10B981";
          if (score >= 60) return "#3B82F6";
          if (score >= 40) return "#EAB308";
          if (score >= 20) return "#F97316";
          return "#EF4444";
        })
        .attr("stroke-width", 2);

      // Entity nodes (rectangles)
      node
        .filter((d) => d.type === "entity")
        .append("rect")
        .attr("x", -18)
        .attr("y", -18)
        .attr("width", 36)
        .attr("height", 36)
        .attr("rx", 4)
        .attr("fill", "#1A1A1A")
        .attr("stroke", "#6B7280")
        .attr("stroke-width", 1.5);

      // Labels
      node
        .append("text")
        .text((d) => {
          const parts = d.label.split(" ");
          return parts.length > 2 ? parts[0] + " " + parts[1] : d.label;
        })
        .attr("y", 32)
        .attr("text-anchor", "middle")
        .attr("fill", "#FAFAFA")
        .attr("font-size", "10px")
        .attr("font-family", "Inter, sans-serif");

      // Click handler
      node.on("click", (_, d) => {
        if (d.type === "politician" && d.slug) {
          router.push(`/politico/${d.slug}`);
        }
      });

      // Tooltip
      node
        .on("mouseover", (event, d) => {
          const rect = containerRef.current!.getBoundingClientRect();
          setTooltip({
            x: event.clientX - rect.left,
            y: event.clientY - rect.top - 10,
            label: d.label,
          });
        })
        .on("mousemove", (event) => {
          const rect = containerRef.current!.getBoundingClientRect();
          setTooltip((prev) =>
            prev ? { ...prev, x: event.clientX - rect.left, y: event.clientY - rect.top - 10 } : null
          );
        })
        .on("mouseout", () => setTooltip(null));

      // Simulation tick
      simulation.on("tick", () => {
        link
          .attr("x1", (d) => ((d.source as unknown as SimNode).x ?? 0))
          .attr("y1", (d) => ((d.source as unknown as SimNode).y ?? 0))
          .attr("x2", (d) => ((d.target as unknown as SimNode).x ?? 0))
          .attr("y2", (d) => ((d.target as unknown as SimNode).y ?? 0));

        node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
      });

      return () => simulation.stop();
    };

    const cleanup = loadD3();
    return () => {
      cleanup.then((fn) => fn?.());
    };
  }, [mounted, data, router]);

  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#2E2E2E] border-t-emerald-500" />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden rounded-xl border border-[#2E2E2E] bg-[#0A0A0A]">
      <svg ref={svgRef} className="h-full w-full" />

      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-[#2E2E2E] bg-[#141414] px-3 py-2 text-xs text-[#FAFAFA] shadow-xl"
          style={{ left: tooltip.x + 12, top: tooltip.y - 12 }}
        >
          {tooltip.label}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 rounded-xl border border-[#2E2E2E] bg-[#141414]/90 p-3 backdrop-blur-sm">
        <p className="mb-2 text-xs font-semibold text-[#FAFAFA]">Legenda</p>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded-full border-2 border-emerald-400 bg-emerald-400/10" />
            <span className="text-xs text-[#6B7280]">Político</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded border border-[#6B7280] bg-[#1A1A1A]" />
            <span className="text-xs text-[#6B7280]">Entidade</span>
          </div>
          {Object.entries(REL_COLORS).slice(0, 4).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2">
              <div className="h-px w-4" style={{ backgroundColor: color }} />
              <span className="text-xs text-[#6B7280] capitalize">{type.replace("_", " ")}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Controls hint */}
      <div className="absolute top-4 right-4 rounded-xl border border-[#2E2E2E] bg-[#141414]/90 p-2 backdrop-blur-sm">
        <p className="text-xs text-[#6B7280]">Scroll para zoom · Arraste para mover · Clique para ver perfil</p>
      </div>
    </div>
  );
};

export default GraphVisualization;
