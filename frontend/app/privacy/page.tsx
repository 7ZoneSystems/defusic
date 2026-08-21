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

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Audio Processing
            </h2>
            <p>
              When you upload an audio file, it is sent to the HearBeat backend
              server for analysis. The server extracts musical and rhythmic
              information such as tempo, beat positions, drum onsets, and bass
              frequencies. This analysis is used to generate haptic feedback
              timelines and visualizations.
            </p>
            <p className="mt-2">
              Audio files are processed in memory and are not stored permanently
              on the server. Temporary analysis output files are cleaned up after
              processing.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Local Data (Anonymous Users)
            </h2>
            <p>
              If you use HearBeat without signing in, your audio file may be
              temporarily stored in your browser&apos;s IndexedDB so that you
              can resume a previous session after a page reload. This data
              stays entirely on your device and is never sent to any server
              unless you choose to analyze it.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Account and Library (Authenticated Users)
            </h2>
            <p>
              If you sign in with Google, HearBeat creates a user account and
              stores your email address and display name from your Google
              profile. This is used to identify you and manage your library.
            </p>
            <p className="mt-2">
              Authenticated users can save songs and their analysis results to a
              personal library. This library metadata (song name, duration,
              analysis mode, timestamps) is stored in a database managed by
              Cohesivity (our backend infrastructure provider).
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Google Sign-In
            </h2>
            <p>
              HearBeat uses Google Sign-In for authentication. When you sign in,
              Google shares your email address, name, and profile picture with
              HearBeat through Cohesivity&apos;s OAuth flow. This information
              is used solely to create and manage your account.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Google Drive Integration (Optional)
            </h2>
            <p>
              HearBeat offers optional Google Drive integration for persistent
              song storage. This feature requires your explicit consent: you
              must click &quot;Connect Google Drive&quot; and approve Drive
              access through Google&apos;s OAuth consent screen.
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
              scope, which is the narrowest scope that allows file operations.
              This scope lets HearBeat access only the files and folders it
              creates — it cannot see your other Drive contents.
            </p>
            <p className="mt-2">
              When you connect Drive, HearBeat creates a{" "}
              <strong>HearBeat/Songs/</strong> folder structure in your Google
              Drive. Your original audio files are uploaded to this folder. The
              Drive file identifiers and folder IDs needed to access these files
              are stored in your HearBeat account metadata.
            </p>
            <p className="mt-2">
              HearBeat stores only the minimum metadata required to reference
              your Drive files: the file ID, folder ID, your email, and account
              identifiers. Your actual audio data lives in your Google Drive,
              not in HearBeat&apos;s database.
            </p>
            <p className="mt-2">
              You can disconnect Google Drive at any time from the Library page.
              Disconnecting removes HearBeat&apos;s access tokens but does not
              delete any files from your Drive.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              OAuth Tokens and Security
            </h2>
            <p>
              All OAuth tokens (both Google Sign-In and Google Drive) are
              handled server-side. Access tokens are stored in httpOnly cookies
              that cannot be accessed by JavaScript. Drive refresh tokens are
              stored in the server database and are never exposed to the
              browser.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Data Sharing with Third Parties
            </h2>
            <p>
              HearBeat does not sell, share, or transmit your personal data to
              third parties. Your audio files and analysis results are processed
              by the HearBeat backend and are not shared with any external
              service.
            </p>
            <p className="mt-2">
              Cohesivity provides the backend infrastructure (database, OAuth)
              and processes data on HearBeat&apos;s behalf under strict
              access controls. Google handles authentication and Drive storage
              under their respective terms of service.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Data Retention and Deletion
            </h2>
            <p>
              Your library data (saved songs, analysis results, haptic presets)
              is retained as long as your account exists. You can delete
              individual songs from your library at any time through the
              Library page.
            </p>
            <p className="mt-2">
              You can disconnect Google Drive at any time. Disconnecting removes
              HearBeat&apos;s access to your Drive but does not delete files
              from your Drive. To delete files from your Drive, you can do so
              directly in Google Drive or use the &quot;Delete from Drive&quot;
              option in the Library.
            </p>
            <p className="mt-2">
              If you wish to delete your entire account and all associated data,
              contact us at the address below.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Contact
            </h2>
            <p>
              For privacy-related questions or to request account/data deletion,
              contact us at{" "}
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
