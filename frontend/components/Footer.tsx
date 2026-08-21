import Link from "next/link";

export default function Footer() {
  return (
    <footer
      className="px-6 py-4 text-xs flex items-center justify-center gap-4"
      style={{
        borderTop: "1px solid var(--border)",
        color: "var(--text-muted)",
      }}
    >
      <Link
        href="/privacy"
        style={{ color: "var(--accent-text)", textDecoration: "none" }}
      >
        Privacy
      </Link>
      <span>&middot;</span>
      <Link
        href="/terms"
        style={{ color: "var(--accent-text)", textDecoration: "none" }}
      >
        Terms
      </Link>
    </footer>
  );
}
