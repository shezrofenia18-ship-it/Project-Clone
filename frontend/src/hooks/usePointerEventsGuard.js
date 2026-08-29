import { useEffect } from "react";

// Selector lapisan Radix yang MEMANG sedang terbuka (dialog, menu, dropdown,
// select/popover yang dirender lewat popper). Selama salah satunya ada,
// `pointer-events: none` di <body> itu wajar dan tidak boleh diusik.
const OPEN_LAYER = [
  '[role="dialog"][data-state="open"]',
  '[role="alertdialog"][data-state="open"]',
  '[role="menu"][data-state="open"]',
  '[data-radix-popper-content-wrapper]',
  '[data-state="open"][data-radix-menu-content]',
  "[data-vaul-drawer][data-state=\"open\"]",
].join(", ");

/**
 * Penjaga: bersihkan `pointer-events: none` yang tertinggal di <body>.
 *
 * MASALAH NYATA DI TABLET/HP: aplikasi ini punya tiga salinan
 * @radix-ui/react-dismissable-layer di node_modules (1.1.7 dari react-dialog,
 * 1.1.19 dari cmdk & vaul). Karena tidak berbagi React context yang sama, gaya
 * `pointer-events: none` yang dipasang saat dialog terbuka kadang TIDAK ikut
 * dibersihkan saat dialog ditutup. Akibatnya sentuhan berikutnya di layar
 * (mis. tombol "Lihat Keranjang" di POS setelah menambah produk) terabaikan
 * tanpa error apa pun — pengguna merasa tombolnya "mati".
 *
 * Penjaga ini hanya membersihkan bila BENAR-BENAR tidak ada lapisan yang terbuka,
 * jadi perilaku dialog yang normal tidak terganggu.
 */
export default function usePointerEventsGuard() {
  useEffect(() => {
    const clear = () => {
      const body = document.body;
      if (!body || body.style.pointerEvents !== "none") return;
      if (document.querySelector(OPEN_LAYER)) return;
      body.style.removeProperty("pointer-events");
    };

    const observer = new MutationObserver(clear);
    observer.observe(document.body, { attributes: true, attributeFilter: ["style"] });
    // Jaring pengaman: animasi tutup Radix ~150-200ms, jadi 250ms sudah aman
    // dan bebannya tidak terasa (hanya membaca satu properti gaya).
    const timer = setInterval(clear, 250);

    return () => {
      observer.disconnect();
      clearInterval(timer);
    };
  }, []);
}
