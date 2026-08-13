// Logo Sonar / Drive Data — tile em degradê verde→azul com chevrons (movimento/"drive").
// Placeholder limpo. Para o logo oficial, troque o conteúdo do <svg> pelo arquivo real.
// Uso: <Logo size={36} />
export function Logo({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Sonar por Drive Data"
    >
      <defs>
        <linearGradient id="ddTile" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3FD07C" />
          <stop offset="0.5" stopColor="#17B6C6" />
          <stop offset="1" stopColor="#1E86E0" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="13" fill="url(#ddTile)" />
      <path
        d="M17 16 L25 24 L17 32"
        stroke="#ffffff"
        strokeWidth="4.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M25 16 L33 24 L25 32"
        stroke="#ffffff"
        strokeOpacity="0.55"
        strokeWidth="4.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default Logo;
