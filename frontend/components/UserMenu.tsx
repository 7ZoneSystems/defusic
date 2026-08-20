"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function UserMenu() {
  const { user, loading, login, logout } = useAuth();
  const [open, setOpen] = useState(false);

  if (loading) return null;

  if (!user) {
    return (
      <button
        onClick={() => login()}
        className="text-xs px-3 py-1.5 rounded-sm transition-opacity hover:opacity-80"
        style={{
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          fontFamily: "var(--font-geist-mono)",
        }}
      >
        Sign in
      </button>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs px-2 py-1 rounded-sm transition-opacity hover:opacity-80"
        style={{
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          fontFamily: "var(--font-geist-mono)",
        }}
      >
        {user.picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={user.picture}
            alt=""
            className="w-4 h-4 rounded-full"
          />
        ) : (
          <span className="w-4 h-4 rounded-full bg-accent inline-block" />
        )}
        <span className="hidden sm:inline">{user.name || user.email}</span>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          <div
            className="absolute right-0 top-full mt-1 z-50 min-w-[160px] py-1 rounded-sm"
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--border)",
              boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            }}
          >
            <div
              className="px-3 py-2 text-xs"
              style={{
                color: "var(--text-muted)",
                borderBottom: "1px solid var(--border)",
              }}
            >
              {user.email}
            </div>
            <a
              href="/library"
              className="block px-3 py-2 text-xs hover:bg-accent/50 transition-colors"
              style={{ color: "var(--text-primary)" }}
              onClick={() => setOpen(false)}
            >
              Library
            </a>
            <button
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="w-full text-left px-3 py-2 text-xs hover:bg-accent/50 transition-colors"
              style={{ color: "var(--text-primary)" }}
            >
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
