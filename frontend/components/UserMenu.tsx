"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useGoogleDrive } from "@/lib/drive";

export default function UserMenu() {
  const { user, loading, login, logout, keepSignedIn, setKeepSignedIn } = useAuth();
  const {
    connected: driveConnected,
    disconnect: driveDisconnect,
    loading: driveLoading,
    initialized: driveInitialized,
    refresh: driveRefresh,
  } = useGoogleDrive();
  const [open, setOpen] = useState(false);

  // Lazily check Drive status only when user opens account menu
  const handleToggle = () => {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (nextOpen && user && !driveInitialized && !driveLoading) {
      driveRefresh();
    }
  };

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
        onClick={handleToggle}
        className="flex items-center gap-1 text-xs px-1.5 py-1 rounded-sm transition-opacity hover:opacity-80"
        style={{
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
        }}
        aria-label="Account"
      >
        {user.picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={user.picture}
            alt=""
            className="w-5 h-5 rounded-full"
          />
        ) : (
          <span className="w-5 h-5 rounded-full bg-accent inline-block" />
        )}
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          <div
            className="absolute right-0 top-full mt-1 z-50 min-w-[180px] py-1 rounded-sm"
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--border)",
              boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            }}
          >
            <a
              href="/library"
              className="block px-3 py-2 text-xs hover:bg-accent/50 transition-colors"
              style={{ color: "var(--text-primary)" }}
              onClick={() => setOpen(false)}
            >
              Library
            </a>
            <div
              className="px-3 py-2 text-xs"
              style={{
                color: (!driveInitialized || driveLoading)
                  ? "var(--text-muted)"
                  : driveConnected
                    ? "var(--success)"
                    : "var(--text-muted)",
                borderBottom: "1px solid var(--border)",
              }}
            >
              {!driveInitialized || driveLoading
                ? "Checking Drive..."
                : driveConnected
                  ? "Drive connected"
                  : "Drive not connected"}
            </div>
            {driveInitialized && !driveLoading && driveConnected && (
              <button
                onClick={() => {
                  setOpen(false);
                  driveDisconnect();
                }}
                className="w-full text-left px-3 py-2 text-xs hover:bg-accent/50 transition-colors"
                style={{ color: "var(--text-primary)" }}
              >
                Disconnect Drive
              </button>
            )}
            <label
              className="flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-accent/50 transition-colors"
              style={{ color: "var(--text-primary)", borderBottom: "1px solid var(--border)" }}
            >
              <input
                type="checkbox"
                checked={keepSignedIn}
                onChange={(e) => setKeepSignedIn(e.target.checked)}
                className="w-3 h-3"
              />
              Keep me signed in
            </label>
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
