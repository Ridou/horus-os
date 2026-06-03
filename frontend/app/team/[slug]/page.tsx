import { AgentDetailView } from "./AgentDetailView";

/**
 * Pre-render the five starter-agent detail pages as static HTML at build time.
 * The AgentDetailView client component fetches live data at runtime, so the
 * static shell works against any backend without redeployment.
 */
export function generateStaticParams() {
  return [
    { slug: "coordinator" },
    { slug: "engineer" },
    { slug: "researcher" },
    { slug: "writer" },
    { slug: "operator" },
  ];
}

export default async function AgentSlugPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <AgentDetailView slug={slug} />;
}
