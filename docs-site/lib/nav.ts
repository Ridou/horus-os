/**
 * The documentation information architecture.
 *
 * This is the single source of truth for the sidebar, breadcrumbs, and
 * prev/next pagination. Each `slug` maps to a markdown file at
 * `content/docs/<slug>.md`. Keep this list ordered the way it should read.
 */

export interface NavItem {
  title: string;
  /** Path under content/docs, also the URL path. e.g. "guides/cli". */
  slug: string;
}

export interface NavSection {
  label: string;
  /** lucide-react icon name, resolved in the Sidebar. */
  icon: string;
  items: NavItem[];
}

export const NAV: NavSection[] = [
  {
    label: "Getting Started",
    icon: "Rocket",
    items: [
      { title: "Introduction", slug: "getting-started/introduction" },
      { title: "Installation", slug: "getting-started/installation" },
      { title: "Quickstart", slug: "getting-started/quickstart" },
      { title: "Your first team run", slug: "getting-started/first-team-run" },
      { title: "Configuration", slug: "getting-started/configuration" },
    ],
  },
  {
    label: "Core Concepts",
    icon: "Boxes",
    items: [
      { title: "Architecture", slug: "concepts/architecture" },
      { title: "The agent team", slug: "concepts/agent-team" },
      { title: "The vault", slug: "concepts/the-vault" },
      { title: "Traces and observability", slug: "concepts/traces-and-observability" },
      { title: "Tasks and scheduling", slug: "concepts/tasks-and-scheduling" },
    ],
  },
  {
    label: "Guides",
    icon: "BookOpen",
    items: [
      { title: "Using the CLI", slug: "guides/cli" },
      { title: "Using the dashboard", slug: "guides/dashboard" },
      { title: "Editing your vault", slug: "guides/editing-your-vault" },
      { title: "Autonomous research", slug: "guides/autonomous-research" },
      { title: "Scheduling agents", slug: "guides/scheduling-agents" },
      { title: "Running as a service", slug: "guides/running-as-a-service" },
      { title: "Remote access", slug: "guides/remote-access" },
    ],
  },
  {
    label: "Integrations",
    icon: "Plug",
    items: [
      { title: "Overview", slug: "integrations/overview" },
      { title: "Discord", slug: "integrations/discord" },
      { title: "Slack", slug: "integrations/slack" },
      { title: "Email", slug: "integrations/email" },
      { title: "Calendar", slug: "integrations/calendar" },
      { title: "MCP servers", slug: "integrations/mcp" },
      { title: "Web access", slug: "integrations/web-access" },
      { title: "GitHub", slug: "integrations/github" },
      { title: "Supabase", slug: "integrations/supabase" },
    ],
  },
  {
    label: "Extending horus-os",
    icon: "Puzzle",
    items: [
      { title: "Plugins", slug: "extending/plugins" },
      { title: "Plugin security", slug: "extending/plugin-security" },
      { title: "Writing an adapter", slug: "extending/writing-an-adapter" },
      { title: "Manifest reference", slug: "extending/manifest-reference" },
    ],
  },
  {
    label: "Deployment & Operations",
    icon: "Server",
    items: [
      { title: "Deploy to Vercel", slug: "operations/deploy-to-vercel" },
      { title: "Observability", slug: "operations/observability" },
      { title: "OpenTelemetry", slug: "operations/opentelemetry" },
      { title: "Security model", slug: "operations/security" },
      { title: "Maintainer runbook", slug: "operations/maintainer-runbook" },
    ],
  },
  {
    label: "Reference",
    icon: "FileCode",
    items: [
      { title: "CLI reference", slug: "reference/cli-reference" },
      { title: "Configuration reference", slug: "reference/configuration" },
      { title: "Environment variables", slug: "reference/environment-variables" },
      { title: "Schema & migrations", slug: "reference/migrations" },
      { title: "Changelog", slug: "reference/changelog" },
    ],
  },
  {
    label: "Project",
    icon: "Users",
    items: [
      { title: "Contributing", slug: "project/contributing" },
      { title: "Code of conduct", slug: "project/code-of-conduct" },
      { title: "Security policy", slug: "project/security-policy" },
      { title: "Roadmap", slug: "project/roadmap" },
    ],
  },
];

/** Flatten the nav into reading order, for prev/next pagination. */
export const FLAT_NAV: NavItem[] = NAV.flatMap((s) => s.items);

export function findNavPosition(slug: string): {
  prev: NavItem | null;
  next: NavItem | null;
  section: NavSection | null;
  item: NavItem | null;
} {
  const index = FLAT_NAV.findIndex((i) => i.slug === slug);
  const section =
    NAV.find((s) => s.items.some((i) => i.slug === slug)) ?? null;
  const item = index >= 0 ? FLAT_NAV[index] : null;
  return {
    prev: index > 0 ? FLAT_NAV[index - 1] : null,
    next: index >= 0 && index < FLAT_NAV.length - 1 ? FLAT_NAV[index + 1] : null,
    section,
    item,
  };
}
