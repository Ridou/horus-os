import { ChevronRight } from "lucide-react";

/** Section > Page breadcrumb above the article title. */
export function Breadcrumbs({
  section,
  title,
}: {
  section: string | null;
  title: string;
}) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="mb-4 flex items-center gap-1.5 font-mono text-xs text-text-muted"
    >
      {section && (
        <>
          <span>{section}</span>
          <ChevronRight className="h-3 w-3" />
        </>
      )}
      <span className="text-text-secondary">{title}</span>
    </nav>
  );
}
