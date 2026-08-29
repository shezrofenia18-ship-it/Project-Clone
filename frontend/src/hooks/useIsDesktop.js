import { useEffect, useState } from "react";

/**
 * Mendeteksi lebar layar >= 1024px (breakpoint `lg` Tailwind).
 *
 * Dipakai POS untuk merender keranjang HANYA SATU KALI: sidebar di desktop, atau
 * bar bawah + panel geser di HP/Tablet. Kalau memakai `hidden lg:flex` saja, kedua
 * versi tetap ada di DOM sehingga data-testid & kontrol form jadi ganda (membingungkan
 * pembaca layar dan pengujian otomatis).
 */
export default function useIsDesktop(query = "(min-width: 1024px)") {
  const [match, setMatch] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = (e) => setMatch(e.matches);
    setMatch(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);

  return match;
}
