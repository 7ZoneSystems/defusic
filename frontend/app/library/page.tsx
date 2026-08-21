"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useGoogleDrive } from "@/lib/drive";
import {
  deleteLibrarySong,
  fetchLibrarySongs,
  getDriveDownloadUrl,
  deleteDriveFile,
  listDriveSongs,
  analyzeDriveSong,
  reprocessLibrarySong,
  LibrarySong,
  DriveSongFile,
} from "@/lib/api";
import DriveConnect from "@/components/DriveConnect";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import {
  HardDrive,
  Download,
  Trash2,
  Play,
  Music,
  Drum,
  RefreshCw,
  Loader2,
} from "lucide-react";

type MergedSong = {
  id: number;
  filename: string;
  file_hash: string;
  file_size: number;
  duration_seconds: number | null;
  analysis_mode: string;
  has_analysis: boolean;
  drive_file_id: string | null;
  analysis_drive_file_id?: string | null;
  created_at: string | null;
  last_played: string | null;
  source: "both" | "db" | "drive";
  drive_file?: DriveSongFile;
};

function LibraryContent() {
  const { user, loading: authLoading, login } = useAuth();
  const {
    connected: driveConnected,
    loading: driveLoading,
    initialized: driveInitialized,
    refresh: refreshDrive,
  } = useGoogleDrive();

  const [dbSongs, setDbSongs] = useState<LibrarySong[]>([]);
  const [driveSongs, setDriveSongs] = useState<DriveSongFile[]>([]);
  const [songsLoading, setSongsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingFileId, setProcessingFileId] = useState<string | null>(null);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);

  // Lazy initialize Drive status when authenticated user opens Library
  useEffect(() => {
    if (authLoading || !user) return;
    if (!driveInitialized && !driveLoading) {
      refreshDrive();
    }
  }, [authLoading, user, driveInitialized, driveLoading, refreshDrive]);

  // Fetch DB songs
  const fetchDbSongs = useCallback(async () => {
    try {
      const data = await fetchLibrarySongs();
      setDbSongs(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load library");
    }
  }, []);

  // Fetch Drive songs
  const fetchDriveSongs = useCallback(async () => {
    if (!driveConnected) return;
    try {
      const data = await listDriveSongs();
      setDriveSongs(data);
    } catch (e) {
      console.warn("Failed to list Drive songs:", e);
    }
  }, [driveConnected]);

  // Fetch library songs only AFTER authentication and Drive state are resolved
  useEffect(() => {
    if (authLoading || !user || !driveInitialized || driveLoading) return;

    let active = true;
    Promise.resolve().then(() => {
      if (!active) return;
      setSongsLoading(true);
      Promise.all([
        fetchDbSongs(),
        driveConnected ? fetchDriveSongs() : Promise.resolve(),
      ]).finally(() => {
        if (active) setSongsLoading(false);
      });
    });

    return () => { active = false; };
  }, [authLoading, user, driveInitialized, driveLoading, driveConnected, fetchDbSongs, fetchDriveSongs]);

  const loading = authLoading || driveLoading || songsLoading;

  // Merge DB songs with Drive files by filename matching
  const mergedSongs = useMemo(() => {
    const result: MergedSong[] = [];
    const dbByHash = new Map<string, LibrarySong>();
    const dbByFilename = new Map<string, LibrarySong>();

    for (const song of dbSongs) {
      dbByHash.set(song.file_hash, song);
      dbByFilename.set(song.filename.toLowerCase(), song);
    }

    const matchedDriveIds = new Set<string>();

    // First: add all DB songs
    for (const song of dbSongs) {
      const isDrive = !!song.drive_file_id;
      result.push({
        ...song,
        source: isDrive ? "both" : "db",
      });
      if (isDrive && song.drive_file_id) matchedDriveIds.add(song.drive_file_id);
    }

    // Second: add Drive files not in DB
    for (const driveFile of driveSongs) {
      if (matchedDriveIds.has(driveFile.id)) continue;

      // Try to match by filename
      const match = dbByFilename.get(driveFile.name.toLowerCase());
      if (match) {
        // Already added as DB song, skip
        matchedDriveIds.add(driveFile.id);
        continue;
      }

      // Unmatched Drive file - add as unprocessed
      result.push({
        id: -1,
        filename: driveFile.name,
        file_hash: "",
        file_size: parseInt(driveFile.size || "0", 10),
        duration_seconds: null,
        analysis_mode: "music",
        has_analysis: false,
        drive_file_id: driveFile.id,
        created_at: driveFile.createdTime,
        last_played: null,
        source: "drive",
        drive_file: driveFile,
      });
    }

    return result;
  }, [dbSongs, driveSongs]);

  const handleDelete = async (song: MergedSong) => {
    if (song.id < 0) return;
    try {
      await deleteLibrarySong(song.id);
      setDbSongs((prev) => prev.filter((s) => s.id !== song.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleDeleteFromDrive = async (song: MergedSong) => {
    const fileId = song.drive_file_id;
    if (!fileId) return;
    if (
      !window.confirm(
        `Delete "${song.filename}" from your Google Drive? This cannot be undone.`
      )
    )
      return;
    try {
      await deleteDriveFile(fileId);
      if (song.id >= 0) {
        setDbSongs((prev) =>
          prev.map((s) =>
            s.id === song.id ? { ...s, drive_file_id: null } : s
          )
        );
      }
      setDriveSongs((prev) => prev.filter((f) => f.id !== fileId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete from Drive");
    }
  };

  const handleProcessDrive = async (song: MergedSong) => {
    if (!song.drive_file_id) return;
    setProcessingFileId(song.drive_file_id);
    setError(null);
    try {
      const result = await analyzeDriveSong(song.drive_file_id, "music");
      if (result.status === "already_analyzed") {
        // Refresh to pick up the match
        await fetchDbSongs();
      } else {
        // Refresh to get the new DB entry
        await fetchDbSongs();
        await fetchDriveSongs();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to process song");
    } finally {
      setProcessingFileId(null);
    }
  };

  const handleReprocess = async (song: MergedSong) => {
    if (song.id < 0) return;
    setReprocessingId(song.id);
    setError(null);
    try {
      await reprocessLibrarySong(song.id, song.analysis_mode);
      await fetchDbSongs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reprocess");
    } finally {
      setReprocessingId(null);
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return null;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // --- Phase 1: Checking authentication ---
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--font-geist-mono)" }}>
          <Loader2 size={16} className="animate-spin" />
          <span>Checking account...</span>
        </div>
      </div>
    );
  }

  // --- Phase 2: Unauthenticated ---
  if (!user) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
        <Header backHref="/" backLabel="Main" />
        <div className="flex flex-col items-center justify-center gap-6" style={{ minHeight: "calc(100vh - 60px)" }}>
          <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Your Library
          </h1>
          <p style={{ color: "var(--text-muted)" }}>
            Sign in to save and access your analyzed tracks.
          </p>
          <button
            onClick={() => login("/library")}
            className="px-6 py-3 rounded-sm transition-opacity hover:opacity-90"
            style={{
              background: "var(--bg-primary)",
              color: "var(--text-primary)",
              border: "1px solid var(--border)",
              fontFamily: "var(--font-geist-mono)",
            }}
          >
            Sign in with Google
          </button>
        </div>
        <Footer />
      </div>
    );
  }

  // --- Phase 3: Checking Google Drive status ---
  if (!driveInitialized || driveLoading) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
        <Header backHref="/" backLabel="Main" />
        <div
          className="flex flex-col items-center justify-center px-6 gap-3"
          style={{ minHeight: "calc(100vh - 60px)" }}
        >
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--font-geist-mono)" }}>
            <Loader2 size={16} className="animate-spin" />
            <span>Checking Google Drive...</span>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  // --- Phase 4: Drive not connected ---
  if (!driveConnected) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
        <Header backHref="/" backLabel="Main" />
        <div
          className="flex flex-col items-center justify-center px-6"
          style={{ minHeight: "calc(100vh - 60px)" }}
        >
          <DriveConnect variant="full" />
        </div>
        <Footer />
      </div>
    );
  }

  // --- Phase 5: Drive connected + empty songs ---
  if (driveConnected && !songsLoading && mergedSongs.length === 0) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
        <Header backHref="/" backLabel="Main" />
        <div
          className="flex flex-col items-center justify-center px-6 gap-4"
          style={{ minHeight: "calc(100vh - 60px)" }}
        >
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--success)" }}>
            <HardDrive size={16} />
            <span>Your Drive is connected</span>
          </div>
          <p className="text-sm text-center max-w-md" style={{ color: "var(--text-muted)" }}>
            No HearBeat songs yet. Analyze a track or drop audio files into your HearBeat/Songs folder on Google Drive.
          </p>
        </div>
        <Footer />
      </div>
    );
  }

  // --- Phase 6: Drive connected with songs (or loading songs) ---
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      <Header backHref="/" backLabel="Main" />
      <div className="p-6 max-w-4xl mx-auto" style={{ minHeight: "calc(100vh - 60px)" }}>
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Your Library
          </h1>
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--success)" }}>
            <HardDrive size={14} />
            <span>Drive connected</span>
          </div>
        </div>

        {error && (
          <div
            className="mb-4 p-3 rounded text-sm"
            style={{ background: "var(--danger-surface, var(--accent-surface))", color: "var(--danger, var(--accent-text))" }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 py-12 justify-center" style={{ color: "var(--text-muted)" }}>
            <Loader2 size={16} className="animate-spin" />
            <span>Loading library...</span>
          </div>
        ) : (
          <div className="space-y-2">
            {mergedSongs.map((song) => {
              const key = song.id >= 0 ? `db-${song.id}` : `drive-${song.drive_file_id}`;
              const isProcessed = song.has_analysis;
              const isUnprocessedDrive =
                song.source === "drive" && !song.has_analysis;
              const isProcessing = isUnprocessedDrive && processingFileId === song.drive_file_id;
              const isReprocessing = reprocessingId === song.id;

              return (
                <div
                  key={key}
                  className="flex items-center justify-between p-4 rounded-md border transition-colors"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--bg-secondary, var(--bg-primary))",
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <p
                      className="font-medium truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {song.filename}
                    </p>
                    <div
                      className="flex flex-wrap gap-x-4 gap-y-1 text-xs mt-1"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {song.duration_seconds ? (
                        <span>{formatDuration(song.duration_seconds)}</span>
                      ) : (
                        song.file_size > 0 && <span>{formatSize(song.file_size)}</span>
                      )}

                      {/* Status badge */}
                      <span
                        className="px-1.5 py-0.5 rounded-sm"
                        style={{
                          background: isProcessed
                            ? "var(--success-surface, rgba(34,197,94,0.1))"
                            : "var(--warning-surface, rgba(234,179,8,0.1))",
                          color: isProcessed
                            ? "var(--success, #22c55e)"
                            : "var(--warning, #eab308)",
                        }}
                      >
                        {isProcessed ? "PROCESSED" : "UNPROCESSED"}
                      </span>

                      {/* Source badge */}
                      {song.source === "both" && (
                        <span className="flex items-center gap-1">
                          <HardDrive size={10} /> Drive + Library
                        </span>
                      )}
                      {song.source === "drive" && (
                        <span className="flex items-center gap-1">
                          <HardDrive size={10} /> Drive
                        </span>
                      )}
                      {song.source === "db" && <span>Library</span>}

                      {song.last_played && (
                        <span>
                          Played {new Date(song.last_played).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 ml-4 shrink-0">
                    {isProcessed && (
                      <>
                        {/* Processed: Play actions */}
                        <a
                          href={`/?library=${song.id}`}
                          className="flex items-center gap-1 px-2 py-1 text-xs rounded-sm transition-colors"
                          style={{
                            color: "var(--text-primary)",
                            border: "1px solid var(--border)",
                          }}
                          title="Open in Music mode"
                        >
                          <Music size={12} />
                          <span className="hidden sm:inline">Music</span>
                        </a>
                        <a
                          href={`/?library=${song.id}&mode=drumming`}
                          className="flex items-center gap-1 px-2 py-1 text-xs rounded-sm transition-colors"
                          style={{
                            color: "var(--text-primary)",
                            border: "1px solid var(--border)",
                          }}
                          title="Open in Drumming mode"
                        >
                          <Drum size={12} />
                          <span className="hidden sm:inline">Drumming</span>
                        </a>

                        {/* Reprocess (secondary) */}
                        <button
                          onClick={() => handleReprocess(song)}
                          disabled={isReprocessing}
                          className="p-1.5 rounded-sm transition-colors"
                          style={{ color: "var(--text-muted)" }}
                          title="Reprocess song"
                          aria-label={`Reprocess ${song.filename}`}
                        >
                          {isReprocessing ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <RefreshCw size={14} />
                          )}
                        </button>
                      </>
                    )}

                    {isUnprocessedDrive && (
                      <button
                        onClick={() => handleProcessDrive(song)}
                        disabled={isProcessing}
                        className="flex items-center gap-1 px-2 py-1 text-xs rounded-sm transition-colors"
                        style={{
                          background: "var(--bg-primary)",
                          color: "var(--text-primary)",
                          border: "1px solid var(--border)",
                        }}
                        title={`Process ${song.filename}`}
                        aria-label={`Process ${song.filename}`}
                      >
                        {isProcessing ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Play size={12} />
                        )}
                        <span>Process</span>
                      </button>
                    )}

                    {/* Download from Drive */}
                    {song.drive_file_id && (
                      <a
                        href={getDriveDownloadUrl(song.drive_file_id)}
                        className="p-1.5 rounded-sm transition-colors"
                        style={{ color: "var(--text-muted)" }}
                        title="Download from Drive"
                        aria-label={`Download ${song.filename} from Drive`}
                      >
                        <Download size={14} />
                      </a>
                    )}

                    {/* Delete from Drive (distinct from Remove) */}
                    {song.drive_file_id && (
                      <button
                        onClick={() => handleDeleteFromDrive(song)}
                        className="p-1.5 rounded-sm transition-colors"
                        style={{ color: "var(--text-muted)" }}
                        title="Delete from Google Drive (keeps in library)"
                        aria-label={`Delete ${song.filename} from Google Drive`}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}

                    {/* Remove from library */}
                    {song.id >= 0 && (
                      <button
                        onClick={() => handleDelete(song)}
                        className="px-2 py-1 text-xs rounded-sm transition-colors"
                        style={{
                          color: "var(--danger, #ef4444)",
                          background: "transparent",
                        }}
                        title="Remove from library"
                        aria-label={`Remove ${song.filename} from library`}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
          <p style={{ color: "var(--text-muted)" }}>Loading...</p>
        </div>
      }
    >
      <LibraryContent />
    </Suspense>
  );
}
