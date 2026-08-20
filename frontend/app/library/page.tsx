"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  deleteLibrarySong,
  fetchLibrarySongs,
  LibrarySong,
} from "@/lib/api";

export default function LibraryPage() {
  const { user, loading: authLoading, login } = useAuth();
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

  const handleDelete = async (songId: number) => {
    try {
      await deleteLibrarySong(songId);
      setSongs((prev) => prev.filter((s) => s.id !== songId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
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
        <span className="text-sm text-muted-foreground">{user.email}</span>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-destructive/10 text-destructive text-sm">
          {error}
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
                  {song.last_played && (
                    <span>
                      Last played {new Date(song.last_played).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleDelete(song.id)}
                className="ml-4 px-3 py-1 text-xs text-destructive hover:bg-destructive/10 rounded transition-colors"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
