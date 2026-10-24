'use client';

import React, { useEffect, useState } from 'react';

interface BrandLoaderProps {
  onFinish?: () => void;
  minDurationMs?: number;
}

export function BrandLoader({ onFinish, minDurationMs = 1500 }: BrandLoaderProps) {
  const [fadingOut, setFadingOut] = useState(false);
  const [removed, setRemoved] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setFadingOut(true);
      const exitTimer = setTimeout(() => {
        setRemoved(true);
        if (onFinish) onFinish();
      }, 550);
      return () => clearTimeout(exitTimer);
    }, minDurationMs);

    return () => clearTimeout(timer);
  }, [minDurationMs, onFinish]);

  if (removed) return null;

  return (
    <div
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[#070809] transition-all duration-500 ease-out ${
        fadingOut ? 'opacity-0 scale-[1.02] pointer-events-none' : 'opacity-100 scale-100'
      }`}
    >
      {/* Ambient background flares */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] h-[520px] rounded-full bg-gradient-to-tr from-[#7170ff]/20 via-[#4f46e5]/15 to-transparent blur-[120px] animate-logo-aura" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[280px] h-[280px] rounded-full bg-[#06b6d4]/10 blur-[80px]" />
        {/* Subtle grid in loader */}
        <div className="absolute inset-0 bg-portal-grid opacity-60" />
      </div>

      {/* Main Logo & Title Center Container */}
      <div className="relative z-10 flex flex-col items-center space-y-6">
        {/* Animated Geometric Logo Mark */}
        <div className="relative w-24 h-24 flex items-center justify-center">
          {/* Outer Pulsing Glow Ring */}
          <div className="absolute inset-0 rounded-2xl bg-[#7170ff]/15 blur-md animate-ping opacity-30" />

          {/* Logo Container with glass backdrop */}
          <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-[#181920] to-[#0d0e12] border border-[#7170ff]/40 p-4 shadow-[0_0_40px_rgba(113,112,255,0.35)] flex items-center justify-center">
            {/* SVG PaperTrail Emblem */}
            <svg
              viewBox="0 0 64 64"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="w-12 h-12"
            >
              <defs>
                <linearGradient id="ptGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#9d9cfc" />
                  <stop offset="100%" stopColor="#7170ff" />
                </linearGradient>
                <linearGradient id="ptGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="100%" stopColor="#818cf8" />
                </linearGradient>
              </defs>

              {/* Lower document fold layer */}
              <path
                d="M14 20C14 16.6863 16.6863 14 20 14H36L50 28V46C50 49.3137 47.3137 52 44 52H20C16.6863 52 14 49.3137 14 46V20Z"
                stroke="url(#ptGrad1)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="opacity-75"
              />

              {/* Forefront paper layer / trail lines */}
              <path
                d="M22 28H34M22 36H42M22 44H38"
                stroke="url(#ptGrad2)"
                strokeWidth="2.2"
                strokeLinecap="round"
              />

              {/* Verified Scientific Seal Dot */}
              <circle cx="42" cy="22" r="3.5" fill="#7170ff" className="animate-pulse" />
              <circle cx="42" cy="22" r="6.5" stroke="#7170ff" strokeWidth="1" className="opacity-40 animate-ping" />
            </svg>
          </div>
        </div>

        {/* Title and Tagline emerging from the logo */}
        <div className="flex flex-col items-center space-y-2 text-center animate-title-slide">
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-[#f7f8f8] to-[#9d9cfc] text-transparent bg-clip-text">
              PaperTrail
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-[#7170ff]/15 border border-[#7170ff]/30 text-[#9d9cfc] uppercase tracking-wider">
              v2.0
            </span>
          </div>

          <p className="text-xs font-mono tracking-[0.22em] text-[#8b8f98] uppercase">
            Scientific Integrity Platform
          </p>

          {/* High-tech Scanning Light Beam */}
          <div className="relative w-44 h-[2px] bg-[#ffffff10] rounded-full overflow-hidden mt-3">
            <div className="absolute inset-y-0 w-20 bg-gradient-to-r from-transparent via-[#7170ff] to-transparent animate-beam-scan" />
          </div>
        </div>
      </div>
    </div>
  );
}
