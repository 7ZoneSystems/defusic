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
      // Clean up URL params
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
      <button
        onClick={disconnect}
        className="flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-sm
                   hover:bg-accent transition-colors"
      >
        <Unplug size={14} />
        <span>Disconnect Drive</span>
      </button>
    );
  }

  return (
    <button
      onClick={connect}
      className="flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-sm
                 bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
    >
      <Plug size={14} />
      <span>Connect Google Drive</span>
    </button>
  );
}
