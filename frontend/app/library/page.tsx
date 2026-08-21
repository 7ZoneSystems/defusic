"use client";

import { Suspense, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useGoogleDrive } from "@/lib/drive";
import {
  deleteLibrarySong,
  fetchLibrarySongs,
  getDriveDownloadUrl,
  deleteDriveFile,
  LibrarySong,
} from "@/lib/api";
import DriveConnect from "@/components/DriveConnect";
import { HardDrive, Download, Trash2 } from "lucide-react";

function LibraryContent() {
  const { user, loading: authLoading, login } = useAuth();
  const { connected: driveConnected } = useGoogleDrive();
  const [songs, setSongs] = useState<LibrarySong[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      fetchLibrarySongs()
        .then((data) => {
          setSongs(data);
          setError(null);
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : "Failed to load library");
        })
        .finally(() => setLoading(false));
    }
  }, [authLoading, user]);

  const handleDelete = async (song: LibrarySong) => {
    try {
      await deleteLibrarySong(song.id);
      setSongs((prev) => prev.filter((s) => s.id !== song.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleDeleteFromDrive = async (song: LibrarySong) => {
    if (!song.drive_file_id) return;
    if (!window.confirm(`Delete "${song.filename}" from your Google Drive? This cannot be undone.`)) return;
    try {
      await deleteDriveFile(song.drive_file_id);
      setSongs((prev) =>
        prev.map((s) => (s.id === song.id ? { ...s, drive_file_id: null } : s))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete from Drive");
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-6">
        <h1 className="text-2xl font-semibold">Your Library</h1>
        <p className="text-muted-foreground">
          Sign in to save and access your analyzed tracks.
        </p>
        <button
          onClick={() => login("/library")}
          className="px-6 py-3 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity"
        >
          Sign in with Google
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold">Your Library</h1>
        <div className="flex items-center gap-4">
          <DriveConnect />
          <span className="text-sm text-muted-foreground">{user.email}</span>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}

      {driveConnected && (
        <div className="mb-4 p-3 rounded bg-muted text-sm" style={{ color: "var(--text-secondary)" }}>
          <div className="flex items-center gap-2 mb-1">
            <HardDrive size={14} />
            <span>Songs are saved to your Google Drive under HearBeat/Songs/.</span>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Removing a song from HearBeat does not delete it from Drive.
            Use the trash icon to delete a file from Google Drive permanently.
          </p>
        </div>
      )}

      {loading ? (
        <p className="text-muted-foreground">Loading songs...</p>
      ) : songs.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-muted-foreground mb-2">No songs saved yet.</p>
          <p className="text-sm text-muted-foreground">
            Analyze a track and save it to your library.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {songs.map((song) => (
            <div
              key={song.id}
              className="flex items-center justify-between p-4 rounded-md border border-border hover:bg-accent/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{song.filename}</p>
                <div className="flex gap-4 text-xs text-muted-foreground mt-1">
                  <span>{song.analysis_mode}</span>
                  {song.duration_seconds && (
                    <span>
                      {Math.floor(song.duration_seconds / 60)}:
                      {String(Math.floor(song.duration_seconds % 60)).padStart(2, "0")}
                    </span>
                  )}
                  {song.has_analysis && <span className="text-green-600">Analyzed</span>}
                  {song.drive_file_id && (
                    <span className="flex items-center gap-1">
                      <HardDrive size={10} /> Saved to Drive
                    </span>
                  )}
                  {song.last_played && (
                    <span>
                      Last played {new Date(song.last_played).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 ml-4">
                {song.drive_file_id && (
                  <a
                    href={getDriveDownloadUrl(song.drive_file_id)}
                    className="p-1.5 text-muted-foreground hover:text-foreground rounded transition-colors"
                    title="Download from Drive"
                  >
                    <Download size={14} />
                  </a>
                )}
                {song.drive_file_id && (
                  <button
                    onClick={() => handleDeleteFromDrive(song)}
                    className="p-1.5 text-muted-foreground hover:text-orange-500 rounded transition-colors"
                    title="Delete from Drive only (keeps in library)"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
                <button
                  onClick={() => handleDelete(song)}
                  className="px-3 py-1 text-xs text-destructive hover:bg-destructive/10 rounded transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    }>
      <LibraryContent />
    </Suspense>
  );
}
