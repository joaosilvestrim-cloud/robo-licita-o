// Logo oficial Drive Data (public/logo.png). Uso: <Logo size={36} />
export function Logo({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/logo.png"
      alt="Drive Data"
      width={size}
      height={size}
      className={className}
      style={{ width: size, height: size, objectFit: "contain", display: "block" }}
    />
  );
}

export default Logo;
