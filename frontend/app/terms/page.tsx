import Link from "next/link";

export const metadata = {
  title: "Terms of Service - HearBeat",
  description: "Terms governing the use of the HearBeat music analysis application.",
};

export default function TermsPage() {
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
          Terms of Service
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
              Acceptance of Terms
            </h2>
            <p>
              By accessing or using HearBeat, you agree to these Terms of
              Service. If you do not agree, do not use the application.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              What HearBeat Does
            </h2>
            <p>
              HearBeat is a music analysis application designed to help
              musicians with hearing loss experience bass, beats, and drum
              patterns through haptic feedback. It analyzes uploaded audio files
              to extract tempo, beat positions, drum onsets, bass frequencies,
              and other rhythmic information.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Acceptable Use
            </h2>
            <p>
              You may use HearBeat only for lawful purposes and in accordance
              with these Terms. You agree not to:
            </p>
            <ul className="mt-2 ml-6 list-disc space-y-1">
              <li>
                Upload audio files that you do not have the right to process
              </li>
              <li>
                Use the service to process content that violates applicable law
              </li>
              <li>
                Attempt to interfere with or disrupt the service or its
                infrastructure
              </li>
              <li>
                Use automated tools to access the service in a way that exceeds
                reasonable usage
              </li>
            </ul>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Your Content
            </h2>
            <p>
              You retain full ownership of any audio files you upload to
              HearBeat. By uploading a file, you grant HearBeat a limited
              license to process the file for the purpose of analysis and
              generating haptic feedback. This license ends when you delete the
              file or your session expires.
            </p>
            <p className="mt-2">
              You are responsible for ensuring that you have the necessary
              rights to upload and process any audio content you submit to
              HearBeat.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Accounts
            </h2>
            <p>
              HearBeat uses Google Sign-In for authentication. You are
              responsible for maintaining the security of your Google account.
              HearBeat does not store passwords — authentication is handled
              entirely by Google.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Google Drive Connection
            </h2>
            <p>
              Connecting Google Drive is entirely optional. If you choose to
              connect, you authorize HearBeat to create a HearBeat/Songs/
              folder in your Google Drive and upload audio files to it. You can
              disconnect Drive at any time from the Library page.
            </p>
            <p className="mt-2">
              HearBeat accesses your Drive only through the narrow{" "}
              <code
                className="px-1 py-0.5 rounded text-xs"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                }}
              >
                drive.file
              </code>{" "}
              scope, which limits access to files HearBeat creates. Disconnecting
              Drive does not delete your files.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Analysis and Haptic Output
            </h2>
            <p>
              HearBeat&apos;s analysis results and haptic feedback timelines are
              provided as-is, for informational and accessibility purposes.
              Analysis accuracy depends on audio quality, genre, and recording
              conditions. Haptic output is generated algorithmically and may
              not perfectly represent the original audio.
            </p>
            <p className="mt-2">
              HearBeat is not a substitute for professional audio analysis,
              medical devices, or hearing aids. It is an accessibility tool
              designed to supplement, not replace, existing hearing assistance.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Intellectual Property
            </h2>
            <p>
              The HearBeat application, including its code, design, analysis
              algorithms, and haptic mapping systems, is the intellectual
              property of its developers. These Terms do not grant you any
              rights to use HearBeat&apos;s trademarks, logos, or brand
              elements.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Service Availability
            </h2>
            <p>
              HearBeat is provided as a student project. We do not guarantee
              uninterrupted availability, and the service may be unavailable
              at times for maintenance, updates, or infrastructure reasons.
              We are not liable for any downtime or data loss.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Termination
            </h2>
            <p>
              You may stop using HearBeat at any time. If you wish to delete
              your account and associated data, contact us at the address
              below. We may suspend or terminate access to the service at our
              discretion, including for violations of these Terms.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Limitation of Liability
            </h2>
            <p>
              HearBeat is provided as a student project on an &quot;as-is&quot;
              and &quot;as-available&quot; basis. To the maximum extent permitted
              by applicable law, the developers of HearBeat shall not be liable
              for any indirect, incidental, special, consequential, or
              punitive damages, or any loss of profits or data, arising out of
              or related to your use of the service.
            </p>
          </section>

          <section>
            <h2
              className="text-lg font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Changes to These Terms
            </h2>
            <p>
              We may update these Terms from time to time. Continued use of
              HearBeat after changes constitutes acceptance of the updated
              Terms.
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
              For questions about these Terms, contact us at{" "}
              <a
                href="mailto:legal@hearbeat.app"
                style={{ color: "var(--accent-text)" }}
              >
                legal@hearbeat.app
              </a>
              .
            </p>
          </section>
        </div>

        <div
          className="mt-12 pt-6 text-xs"
          style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
        >
          <Link href="/privacy" style={{ color: "var(--accent-text)", textDecoration: "none" }}>
            Privacy Policy
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
