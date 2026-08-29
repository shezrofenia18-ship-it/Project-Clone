// Konstanta tampilan grafik dashboard — dipakai bersama supaya semua grafik
// punya gaya yang sama dan tidak ada objek baru dibuat setiap render.
import { formatRupiahShort } from "@/lib/format";

export const TICK_SM = { fontSize: 11 };
export const TICK_MD = { fontSize: 12 };
export const TOOLTIP_STYLE = { borderRadius: 12, border: "1px solid hsl(var(--border))" };
export const AREA_MARGIN = { left: -10, right: 8 };
export const BAR_MARGIN = { left: -10 };
export const BAR_RADIUS = [6, 6, 0, 0];
export const LEGEND_STYLE = { fontSize: 11 };

export const jtFmt = (v) => `${v / 1000000}jt`;
export const shortFmt = (v) => formatRupiahShort(v).replace("Rp ", "");
