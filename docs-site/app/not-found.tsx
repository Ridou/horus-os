import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-6 text-center">
      <p className="font-mono text-6xl font-bold text-accent-cyan">404</p>
      <h1 className="mt-4 text-xl font-bold text-text-primary">
        This page is not in the vault
      </h1>
      <p className="mt-2 text-sm text-text-secondary">
        The page you are looking for does not exist or has moved.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center gap-2 rounded-md border border-border-subtle bg-bg-secondary px-4 py-2 text-sm font-bold text-text-primary transition-colors hover:border-accent-cyan/40 hover:text-accent-cyan"
      >
        <Home className="h-4 w-4" />
        Back to docs home
      </Link>
    </div>
  );
}
