import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PaperTrail — Cross-Paper Scientific Claim & Contradiction Analysis",
  description: "Automated empirical scientific contradiction analysis, literature discovery, and evidence-grounded claim graphs.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full dark`}
    >
      <body className="min-h-full flex flex-col bg-[#07080a] text-[#f7f8f8] relative antialiased selection:bg-[#7170ff]/30 selection:text-white">
        {/* Background Ambience & Scientific Flares */}
        <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
          {/* Subtle Dot Matrix Blueprint Grid */}
          <div className="absolute inset-0 bg-portal-grid opacity-75" />

          {/* Top Edge Gradient Beam */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[#7170ff]/50 to-transparent" />

          {/* Flare 1: Top-Right Indigo Glow */}
          <div className="absolute -top-32 -right-32 w-[650px] h-[650px] rounded-full bg-[#7170ff]/[0.08] blur-[140px]" />

          {/* Flare 2: Mid-Left Subtle Cyan/Emerald Glow */}
          <div className="absolute top-[35%] -left-40 w-[550px] h-[550px] rounded-full bg-[#06b6d4]/[0.045] blur-[150px]" />

          {/* Flare 3: Bottom-Right Deep Purple Shimmer */}
          <div className="absolute -bottom-40 right-[15%] w-[600px] h-[600px] rounded-full bg-[#818cf8]/[0.05] blur-[160px]" />
        </div>

        {/* Primary Content Container */}
        <div className="relative z-10 flex-1 flex flex-col">
          {children}
        </div>
      </body>
    </html>
  );
}
