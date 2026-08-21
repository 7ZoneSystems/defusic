"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  getDriveStatus,
  exchangeDriveCode,
  disconnectDrive,
} from "./api";
import { useAuth } from "./auth";

interface DriveContextType {
  connected: boolean;
  hasSongs: boolean;
  loading: boolean;
  folderId: string | null;
  songsFolderId: string | null;
  connectionFileId: string | null;
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
  const { loading: authLoading } = useAuth();
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [folderId, setFolderId] = useState<string | null>(null);
  const [songsFolderId, setSongsFolderId] = useState<string | null>(null);
  const [hasSongs, setHasSongs] = useState(false);
  const [connectionFileId, setConnectionFileId] = useState<string | null>(null);
  const fetchVersionRef = useRef(0);

  const refresh = useCallback(async () => {
    const version = ++fetchVersionRef.current;
    try {
      setLoading(true);
      const status = await getDriveStatus();
      if (version !== fetchVersionRef.current) return;
      setConnected(status.connected);
      setHasSongs(status.has_songs);
      setFolderId(status.folder_id);
      setSongsFolderId(status.songs_folder_id);
      setConnectionFileId(status.connection_file_id);
    } catch {
      if (version !== fetchVersionRef.current) return;
      setConnected(false);
      setHasSongs(false);
    } finally {
      if (version === fetchVersionRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [authLoading, refresh]);

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
    setHasSongs(false);
    setFolderId(null);
    setSongsFolderId(null);
    setConnectionFileId(null);
  }, []);

  return (
    <DriveContext.Provider
      value={{ connected, hasSongs, loading, folderId, songsFolderId, connectionFileId, connect, disconnect, exchangeCode, refresh }}
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
