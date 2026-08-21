"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useGoogleDrive } from "@/lib/drive";
import { HardDrive, Plug, Unplug } from "lucide-react";

export default function DriveConnect() {
  const { connected, loading, connect, disconnect, exchangeCode } = useGoogleDrive();
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("drive_code");
    if (code) {
      exchangeCode(code).catch(console.error);
      window.history.replaceState({}, "", "/library");
    }
  }, [searchParams, exchangeCode]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm opacity-50">
        <HardDrive size={16} />
        <span>Checking Drive...</span>
      </div>
    );
  }

  if (connected) {
    return (
      <div className="flex flex-col gap-1">
        <button
          onClick={disconnect}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-sm
                     hover:bg-accent transition-colors"
        >
          <Unplug size={14} />
          <span>Disconnect Drive</span>
        </button>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Your saved songs are stored in your Google Drive under HearBeat/Songs/.
          Disconnecting does not delete your files.
        </p>
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
        <Plug size={14} />
        <span>Connect Google Drive</span>
      </button>
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Optional. HearBeat uses Google Drive only after you authorize access.
        Saved audio stays in your Drive under a dedicated HearBeat/Songs/ folder.
      </p>
    </div>
  );
}
