// Logo Drive Data / Sonar — "D" com corpo verde→azul e duas lâminas de movimento.
// Reprodução vetorial do logo oficial da Drive Data.
// Uso: <Logo size={36} />
export function Logo({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 500 500"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Drive Data"
    >
      <defs>
        <linearGradient id="ddMain" x1="120" y1="20" x2="430" y2="480" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5CE07C" />
          <stop offset="0.5" stopColor="#1FC3CB" />
          <stop offset="1" stopColor="#1E86E0" />
        </linearGradient>
        <linearGradient id="ddBlue" x1="55" y1="95" x2="258" y2="405" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1663C0" />
          <stop offset="1" stopColor="#23AEE8" />
        </linearGradient>
        <linearGradient id="ddGreen" x1="25" y1="175" x2="205" y2="465" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4ADB7E" />
          <stop offset="1" stopColor="#25B58F" />
        </linearGradient>
      </defs>
      {/* lâmina verde (fundo, mais à esquerda) */}
      <path d="M25 175 L110 175 L205 320 L110 465 L25 465 L120 320 Z" fill="url(#ddGreen)" />
      {/* lâmina azul (meio) */}
      <path d="M55 95 L150 95 L258 250 L150 405 L55 405 L163 250 Z" fill="url(#ddBlue)" />
      {/* corpo do D (frente): arco à direita + entalhe apontando à direita */}
      <path d="M100 15 L255 15 A238 238 0 0 1 255 491 L155 491 L262 250 Z" fill="url(#ddMain)" />
    </svg>
  );
}

export default Logo;
