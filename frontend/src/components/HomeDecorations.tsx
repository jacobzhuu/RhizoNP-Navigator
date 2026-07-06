export function HomeDecorations() {
  return (
    <div className="home-decorations" aria-hidden="true">
      <svg className="home-deco home-deco--dna" viewBox="0 0 120 200" fill="none">
        <path
          d="M30 10 C70 30, 50 70, 90 90 S50 150, 70 190"
          stroke="currentColor"
          strokeWidth="2"
          opacity="0.4"
        />
        <path
          d="M90 10 C50 30, 70 70, 30 90 S70 150, 50 190"
          stroke="currentColor"
          strokeWidth="2"
          opacity="0.4"
        />
        {Array.from({ length: 8 }).map((_, i) => (
          <line
            key={i}
            x1={30 + (i % 2) * 60}
            y1={20 + i * 22}
            x2={90 - (i % 2) * 60}
            y2={20 + i * 22}
            stroke="currentColor"
            strokeWidth="1.5"
            opacity="0.3"
          />
        ))}
      </svg>

      <svg className="home-deco home-deco--molecule" viewBox="0 0 100 100" fill="none">
        <circle cx="50" cy="20" r="5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="25" cy="40" r="5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="75" cy="40" r="5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="25" cy="70" r="5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="75" cy="70" r="5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="50" cy="88" r="5" stroke="currentColor" strokeWidth="1.5" />
        <line x1="50" y1="20" x2="25" y2="40" stroke="currentColor" strokeWidth="1.25" />
        <line x1="50" y1="20" x2="75" y2="40" stroke="currentColor" strokeWidth="1.25" />
        <line x1="25" y1="40" x2="75" y2="40" stroke="currentColor" strokeWidth="1.25" />
        <line x1="25" y1="40" x2="25" y2="70" stroke="currentColor" strokeWidth="1.25" />
        <line x1="75" y1="40" x2="75" y2="70" stroke="currentColor" strokeWidth="1.25" />
        <line x1="25" y1="70" x2="50" y2="88" stroke="currentColor" strokeWidth="1.25" />
        <line x1="75" y1="70" x2="50" y2="88" stroke="currentColor" strokeWidth="1.25" />
        <line x1="25" y1="70" x2="75" y2="70" stroke="currentColor" strokeWidth="1.25" />
      </svg>

      <svg className="home-deco home-deco--plant" viewBox="0 0 80 130" fill="none">
        <ellipse cx="40" cy="88" rx="28" ry="9" fill="#8B6914" opacity="0.55" />
        <path d="M40 90 C34 102, 22 108, 14 118" stroke="#a67c52" strokeWidth="2" strokeLinecap="round" opacity="0.65" />
        <path d="M40 90 C44 104, 52 112, 58 120" stroke="#a67c52" strokeWidth="2" strokeLinecap="round" opacity="0.65" />
        <path d="M40 90 V112" stroke="#a67c52" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <path d="M40 88 V48" stroke="#2d8a4e" strokeWidth="3" strokeLinecap="round" />
        <path d="M40 68 C24 62, 16 46, 24 36" stroke="#3cb371" strokeWidth="2.25" fill="none" strokeLinecap="round" />
        <path d="M40 58 C56 52, 64 34, 56 24" stroke="#3cb371" strokeWidth="2.25" fill="none" strokeLinecap="round" />
        <path d="M40 78 C28 74, 22 64, 28 56" stroke="#3cb371" strokeWidth="2" fill="none" strokeLinecap="round" />
        <ellipse cx="22" cy="36" rx="11" ry="7" fill="#4caf6e" opacity="0.85" transform="rotate(-28 22 36)" />
        <ellipse cx="58" cy="24" rx="11" ry="7" fill="#4caf6e" opacity="0.85" transform="rotate(28 58 24)" />
        <ellipse cx="26" cy="56" rx="9" ry="6" fill="#5cbf7e" opacity="0.75" transform="rotate(-18 26 56)" />
      </svg>

      <svg className="home-deco home-deco--wave" viewBox="0 0 1200 100" preserveAspectRatio="none" fill="none">
        <path
          d="M0 55 C200 20, 400 80, 600 50 S1000 15, 1200 45 V100 H0 Z"
          fill="url(#home-wave-gradient)"
          opacity="0.55"
        />
        <defs>
          <linearGradient id="home-wave-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#d8ecfb" />
            <stop offset="1" stopColor="#eef6fd" stopOpacity="0.2" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}
