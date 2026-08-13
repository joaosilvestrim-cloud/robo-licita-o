// Logo Sonar / Drive Data — "D" com duas lâminas de movimento em degradê verde→azul.
// Reprodução vetorial do logo Drive Data. Para fidelidade total, substitua os <path>
// pelo SVG oficial (mesmo viewBox).
// Uso: <Logo size={36} />
export function Logo({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Sonar por Drive Data"
    >
      <defs>
        <linearGradient id="ddBowl" x1="20" y1="6" x2="58" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#48D77F" />
          <stop offset="0.5" stopColor="#18B8C8" />
          <stop offset="1" stopColor="#1E86E0" />
        </linearGradient>
        <linearGradient id="ddBlade" x1="12" y1="15" x2="33" y2="49" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1663C0" />
          <stop offset="1" stopColor="#1EA6E6" />
        </linearGradient>
        <linearGradient id="ddBladeG" x1="4" y1="21" x2="23" y2="47" gradientUnits="userSpaceOnUse">
          <stop stopColor="#46D57F" />
          <stop offset="1" stopColor="#26B48C" />
        </linearGradient>
      </defs>
      {/* lâmina verde (fundo, mais à esquerda) */}
      <path d="M4 21 L12 21 L23 34 L12 47 L4 47 L15 34 Z" fill="url(#ddBladeG)" />
      {/* lâmina azul (meio) */}
      <path d="M12 15 L21 15 L33 32 L21 49 L12 49 L24 32 Z" fill="url(#ddBlade)" />
      {/* corpo do D (frente, lado reto à esquerda + arco à direita) */}
      <path d="M28 6 L39 6 A25 25 0 0 1 39 58 L28 58 Z" fill="url(#ddBowl)" />
    </svg>
  );
}

export default Logo;
