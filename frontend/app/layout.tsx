import type { Metadata } from "next";
import { Geist, Geist_Mono, Caveat } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";
import { AuthProvider } from "@/lib/auth";
import { GoogleDriveProvider } from "@/lib/drive";
import CookieConsent from "@/components/CookieConsent";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HearBeat - Music Analysis Engine",
  description: "Music analysis engine with haptic feedback for hearing-impaired musicians",
  icons: {
    icon: "/favicon.png",
  },
};

/**
 * Inline script that runs before first paint to prevent theme flash.
 * Reads the stored preference and sets data-theme immediately.
 */
const themeScript = `
(function() {
  try {
    var pref = localStorage.getItem('hearbeat-theme');
    var theme = 'dark';
    if (pref === 'light' || pref === 'dark') {
      theme = pref;
    } else if (pref === 'system' || !pref) {
      theme = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', theme);
  } catch(e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${caveat.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <AuthProvider>
            <GoogleDriveProvider>
              {children}
              <CookieConsent />
            </GoogleDriveProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
