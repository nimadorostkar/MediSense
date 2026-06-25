/**
 * Animated sphere logo. `logo-sphere.png` is a 46-frame horizontal sprite strip
 * (7820×170). We step background-position-x across the strip with CSS steps(46).
 * Background sizing + keyframe distance are defined in tailwind.config.js
 * (animation: ring-hero / ring-hdr).
 */
export default function Logo({ size, hero = false }: { size: number; hero?: boolean }) {
  return (
    <div
      aria-label="MediSense"
      role="img"
      className={`ms-logo ${hero ? "animate-ring-hero" : "animate-ring-hdr"}`}
      style={{
        width: size,
        height: size,
        backgroundSize: `auto ${size}px`,
        filter: hero
          ? "contrast(1.05) drop-shadow(0 4px 14px rgba(60,80,140,0.14))"
          : "contrast(1.05)",
        transform: hero ? "scale(1.05)" : undefined,
      }}
    />
  );
}
