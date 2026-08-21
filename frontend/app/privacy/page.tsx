import Link from "next/link";

export const metadata = {
  title: "Privacy Policy - HearBeat",
  description: "How HearBeat handles your data, audio files, and Google account integration.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link
          href="/"
          className="inline-block mb-8 text-sm"
          style={{ color: "var(--accent-text)", textDecoration: "none" }}
        >
          &larr; Back to HearBeat
        </Link>

        <h1
          className="text-3xl font-semibold mb-2"
          style={{ color: "var(--text-primary)" }}
        >
          Privacy Policy
        </h1>
        <p className="text-sm mb-8" style={{ color: "var(--text-muted)" }}>
          Effective date: August 21, 2026
        </p>

        <div
          className="space-y-8 text-sm leading-relaxed"
          style={{ color: "var(--text-secondary)" }}
        >
          {/* ---- What HearBeat Is ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              What HearBeat Is
            </h2>
            <p>
              HearBeat is a music analysis tool that helps musicians with hearing
              loss experience bass, beats, and drum patterns through haptic
              feedback. It runs in your browser and communicates with a backend
              server for audio processing.
            </p>
          </section>

          {/* ---- Authentication ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Authentication
            </h2>
            <p>
              HearBeat uses Google Sign-In for authentication. Signing in is
              optional — you can use the core analysis features without an
              account.
            </p>
            <p className="mt-2">
              If you sign in, Google shares your email address, name, and profile
              picture with HearBeat through our OAuth flow. This information is
              used to create and manage your account and is stored in our
              database.
            </p>
            <p className="mt-2">
              Authenticated users can maintain a persistent personal library of
              saved songs, analysis results, and haptic presets.
            </p>
          </section>

          {/* ---- Audio Analysis ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Audio Analysis
            </h2>
            <p>
              When you upload an audio file, it is sent to the HearBeat backend
              server for analysis. The server extracts musical and rhythmic
              information including beats, drum onsets, kick, bass, and
              sub-bass events, and generates haptic feedback timelines.
            </p>
            <p className="mt-2">
              For anonymous (non-authenticated) users, the original audio file is
              temporarily stored in your browser&apos;s IndexedDB so you can
              resume a session after a page reload. This data stays on your
              device. Analysis results are returned to your browser and are not
              stored permanently on the server.
            </p>
          </section>

          {/* ---- Anonymous / Local Caching ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Anonymous and Local Caching
            </h2>
            <p>
              If you use HearBeat without signing in, your audio file and
              analysis data are stored only in your browser&apos;s IndexedDB.
              This is a local cache that survives page reloads but remains on
              your device.
            </p>
            <p className="mt-2">
              The local cache stores a single file at a time and is overwritten
              when you select a new track. There is no automatic expiration — the
              cached data remains until you select a different file or clear your
              browser data. This cache is not content-addressed: if you upload
              the same file contents with a different filename, it replaces the
              previous cache entry.
            </p>
            <p className="mt-2">
              Anonymous analysis results are not persisted in any cloud storage.
              They exist only in your browser session.
            </p>
          </section>

          {/* ---- User Library ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              User Library (Authenticated Users)
            </h2>
            <p>
              When you are signed in, you can save songs to your personal
              library. The following information is stored in our database:
            </p>
            <ul className="mt-2 ml-6 list-disc space-y-1">
              <li>Song metadata (filename, file size, duration, analysis mode)</li>
              <li>A content hash (SHA-256) used for deduplication</li>
              <li>Analysis status and references</li>
              <li>Saved haptic configuration presets</li>
              <li>Google Drive file identifiers for saved audio</li>
              <li>Timestamps (when the song was saved, last played)</li>
            </ul>
            <p className="mt-2">
              Actual audio files are not stored in our database. Saved songs use
              your connected Google Drive for persistent audio storage (see below).
            </p>
          </section>

          {/* ---- Google Drive ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Google Drive Integration (Optional)
            </h2>
            <p>
              HearBeat offers optional Google Drive integration for storing your
              saved audio files. This feature requires your explicit consent: you
              must click &quot;Connect Google Drive&quot; and approve access
              through Google&apos;s OAuth consent screen.
            </p>
            <p className="mt-2">
              HearBeat requests the{" "}
              <code
                className="px-1 py-0.5 rounded text-xs"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                }}
              >
                drive.file
              </code>{" "}
              scope, which is the narrowest Google Drive scope that allows file
              operations. This scope lets HearBeat create and access only the
              files and folders it creates — it cannot see your other Drive
              contents.
            </p>
            <p className="mt-2">
              When you connect Drive, HearBeat creates a{" "}
              <strong>HearBeat/Songs/</strong> folder in your Google Drive. When
              you save a song, the original audio file is uploaded to this
              folder. The Drive file identifiers needed to reference these files
              are stored in your HearBeat account metadata.
            </p>
            <p className="mt-2">
              You can disconnect Google Drive at any time from the Library page.
              Disconnecting removes HearBeat&apos;s access tokens but does not
              delete any files from your Drive.
            </p>
            <p className="mt-2">
              Removing a song from your HearBeat library removes the metadata
              record. It does not automatically delete the corresponding audio
              file from your Google Drive. You can delete Drive files separately
              through the explicit &quot;Delete from Drive&quot; action or
              directly in Google Drive.
            </p>
          </section>

          {/* ---- OAuth Token Security ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              OAuth Token Security
            </h2>
            <p>
              Google Sign-In tokens are handled entirely server-side. Session
              cookies are httpOnly, secure, and use SameSite=Lax.
            </p>
            <p className="mt-2">
              Google Drive access and refresh tokens are stored server-side and
              encrypted at rest using AES-256-GCM authenticated encryption. A
              server-side encryption key (not stored in the database or source
              code) is used for this encryption.
            </p>
          </section>

          {/* ---- Cohesivity ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Infrastructure Provider
            </h2>
            <p>
              HearBeat uses Cohesivity for account authentication and as the
              database infrastructure provider for storing user accounts, library
              metadata, and haptic presets. Cohesivity processes data on
              HearBeat&apos;s behalf under strict access controls.
            </p>
            <p className="mt-2">
              Your audio files are not stored in Cohesivity. They are either in
              your browser (anonymous session) or in your Google Drive (saved
              library).
            </p>
          </section>

          {/* ---- Data Access ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              What HearBeat Accesses
            </h2>
            <p>
              HearBeat accesses your Google Drive only after you explicitly
              authorize access. It accesses only the files and folders it
              creates within the HearBeat/Songs/ directory. HearBeat does not
              scan, index, or access any other part of your Google Drive.
            </p>
          </section>

          {/* ---- Data Sharing ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Third-Party Services
            </h2>
            <p>
              HearBeat integrates with the following third-party services:
            </p>
            <ul className="mt-2 ml-6 list-disc space-y-1">
              <li>
                <strong>Google</strong> — for authentication (Google Sign-In)
                and, optionally, file storage (Google Drive)
              </li>
              <li>
                <strong>Cohesivity</strong> — for backend infrastructure
                (database, OAuth token management)
              </li>
            </ul>
            <p className="mt-2">
              HearBeat does not sell, share, or transmit your personal data to
              any other third parties. There are no analytics, advertising, or
              tracking services integrated into HearBeat.
            </p>
          </section>

          {/* ---- Data Deletion ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Data Deletion
            </h2>
            <p>
              You can manage your data in the following ways:
            </p>
            <ul className="mt-2 ml-6 list-disc space-y-1">
              <li>
                <strong>Remove from library:</strong> Deletes the song metadata
                record from HearBeat. Does not delete the audio file from your
                Google Drive.
              </li>
              <li>
                <strong>Delete from Drive:</strong> Permanently deletes the audio
                file from your Google Drive. This action cannot be undone.
              </li>
              <li>
                <strong>Disconnect Drive:</strong> Removes HearBeat&apos;s access
                to your Google Drive. Your Drive files are not deleted.
              </li>
              <li>
                <strong>Sign out:</strong> Ends your session. Your library data
                remains in your account for when you sign in again.
              </li>
            </ul>
            <p className="mt-2">
              To request deletion of your entire account and all associated data,
              contact us at the address below.
            </p>
          </section>

          {/* ---- Security ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Security
            </h2>
            <p>
              HearBeat takes the following security measures:
            </p>
            <ul className="mt-2 ml-6 list-disc space-y-1">
              <li>All OAuth tokens are handled server-side, never exposed to the browser</li>
              <li>Session cookies are httpOnly, secure, and SameSite=Lax</li>
              <li>Google Drive tokens are encrypted at rest using AES-256-GCM</li>
              <li>Google Drive access is limited to the narrow drive.file scope</li>
              <li>No secrets are included in the frontend JavaScript bundle</li>
            </ul>
            <p className="mt-2">
              HearBeat does not claim end-to-end encryption, zero data retention,
              or compliance with specific regulatory frameworks.
            </p>
          </section>

          {/* ---- Changes ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Changes to This Policy
            </h2>
            <p>
              We may update this Privacy Policy from time to time. Changes will
              be reflected on this page with an updated effective date.
            </p>
          </section>

          {/* ---- Contact ---- */}
          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Contact
            </h2>
            <p>
              For privacy-related questions or to request account and data
              deletion, contact us at{" "}
              <a
                href="mailto:privacy@hearbeat.app"
                style={{ color: "var(--accent-text)" }}
              >
                privacy@hearbeat.app
              </a>
              .
            </p>
          </section>
        </div>

        <div
          className="mt-12 pt-6 text-xs"
          style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
        >
          <Link href="/terms" style={{ color: "var(--accent-text)", textDecoration: "none" }}>
            Terms of Service
          </Link>
          {" "}&middot;{" "}
          <Link href="/" style={{ color: "var(--accent-text)", textDecoration: "none" }}>
            HearBeat Home
          </Link>
        </div>
      </div>
    </div>
  );
}
