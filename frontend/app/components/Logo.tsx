// Logo Drive Data — "D" com lâminas em degradê verde→azul.
// Uso: <Logo size={36} />
export function Logo({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Drive Data"
    >
      <defs>
        <linearGradient id="ddMain" x1="140" y1="30" x2="450" y2="480" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4FDD7E" />
          <stop offset="0.55" stopColor="#1FBFCB" />
          <stop offset="1" stopColor="#1E86E0" />
        </linearGradient>
        <linearGradient id="ddBlue" x1="90" y1="100" x2="300" y2="420" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1663C0" />
          <stop offset="1" stopColor="#1EA6E6" />
        </linearGradient>
        <linearGradient id="ddGreen" x1="40" y1="170" x2="236" y2="470" gradientUnits="userSpaceOnUse">
          <stop stopColor="#48D680" />
          <stop offset="1" stopColor="#26B48C" />
        </linearGradient>
      </defs>
      {/* lâmina verde (fundo) */}
      <path d="M40 168 L128 168 L236 320 L128 472 L40 472 L148 320 Z" fill="url(#ddGreen)" />
      {/* lâmina azul (meio) */}
      <path d="M96 96 L188 96 L300 256 L188 416 L96 416 L208 256 Z" fill="url(#ddBlue)" />
      {/* corpo do D (frente) */}
      <path d="M168 24 L268 24 A232 232 0 0 1 268 488 L168 488 L280 256 Z" fill="url(#ddMain)" />
    </svg>
  );
}

export default Logo;
