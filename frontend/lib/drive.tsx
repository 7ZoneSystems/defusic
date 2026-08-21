"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  getDriveStatus,
  exchangeDriveCode,
  disconnectDrive,
} from "./api";

interface DriveContextType {
  connected: boolean;
  loading: boolean;
  folderId: string | null;
  songsFolderId: string | null;
  connect: () => void;
  disconnect: () => Promise<void>;
  exchangeCode: (code: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const DriveContext = createContext<DriveContextType | null>(null);

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_DRIVE_CLIENT_ID || "";
const REDIRECT_URI = typeof window !== "undefined"
  ? `${window.location.origin}/auth/drive-callback`
  : "";

export function GoogleDriveProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [folderId, setFolderId] = useState<string | null>(null);
  const [songsFolderId, setSongsFolderId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const status = await getDriveStatus();
      setConnected(status.connected);
      setFolderId(status.folder_id);
      setSongsFolderId(status.songs_folder_id);
    } catch {
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const connect = useCallback(() => {
    const scope = "https://www.googleapis.com/auth/drive.file";
    const params = new URLSearchParams({
      client_id: GOOGLE_CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      response_type: "code",
      scope,
      access_type: "offline",
      prompt: "consent",
    });
    window.open(
      `https://accounts.google.com/o/oauth2/v2/auth?${params}`,
      "_self"
    );
  }, []);

  const exchangeCode = useCallback(
    async (code: string) => {
      await exchangeDriveCode(code);
      await refresh();
    },
    [refresh]
  );

  const disconnect = useCallback(async () => {
    await disconnectDrive();
    setConnected(false);
    setFolderId(null);
    setSongsFolderId(null);
  }, []);

  return (
    <DriveContext.Provider
      value={{ connected, loading, folderId, songsFolderId, connect, disconnect, exchangeCode, refresh }}
    >
      {children}
    </DriveContext.Provider>
  );
}

export function useGoogleDrive() {
  const ctx = useContext(DriveContext);
  if (!ctx) throw new Error("useGoogleDrive must be used within GoogleDriveProvider");
  return ctx;
}
