// Logger ringan untuk jalur error yang SENGAJA ditelan (kuota localStorage,
// JSON rusak, socket sudah tertutup, dsb). Tetap sunyi di produksi supaya
// konsol kasir bersih, tapi terlihat saat pengembangan/debug.
export function devWarn(scope, err) {
  if (process.env.NODE_ENV !== "production") {
    console.warn(`[bam] ${scope}:`, err);
  }
}

export default devWarn;
