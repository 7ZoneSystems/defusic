"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useGoogleDrive } from "@/lib/drive";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { HardDrive } from "lucide-react";

interface DriveConnectProps {
  variant?: "full" | "compact";
}

export default function DriveConnect({ variant = "compact" }: DriveConnectProps) {
  const { connected, loading, initialized, connect, exchangeCode } = useGoogleDrive();
  const { user, loading: authLoading } = useAuth();
  const { resolved: theme } = useTheme();
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("drive_code");
    if (code && !authLoading && user) {
      exchangeCode(code).catch(console.error);
      window.history.replaceState({}, "", "/library");
    }
  }, [searchParams, exchangeCode, authLoading, user]);

  if (loading || (!initialized && user && !authLoading)) {
    return (
      <div className="flex items-center gap-2 text-sm opacity-50">
        <HardDrive size={16} />
        <span>Checking Drive...</span>
      </div>
    );
  }

  if (connected) {
    if (variant === "full") {
      return (
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--success)" }}>
          <HardDrive size={14} />
          <span>Drive connected</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-2 text-sm" style={{ color: "var(--success)" }}>
        <HardDrive size={14} />
        <span>Drive connected</span>
      </div>
    );
  }

  if (variant === "full") {
    const illustrationSrc = theme === "light" ? "/drive_light.png" : "/drive_dark.png";
    return (
      <div className="flex flex-col items-center gap-6">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={illustrationSrc}
          alt="Connect Google Drive to save your songs"
          className="w-full max-w-md h-auto"
          style={{ maxHeight: "50vh", objectFit: "contain" }}
        />
        <button
          onClick={connect}
          className="block transition-opacity hover:opacity-80"
          aria-label="Connect Google Drive"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/drive_connect.png"
            alt="Connect Google Drive"
            className="h-12 w-auto"
          />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={connect}
        className="flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-sm
                   bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <HardDrive size={14} />
        <span>Connect Google Drive</span>
      </button>
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Optional. HearBeat uses Google Drive only after you authorize access.
        Saved audio stays in your Drive under a dedicated HearBeat/Songs/ folder.
      </p>
    </div>
  );
}
