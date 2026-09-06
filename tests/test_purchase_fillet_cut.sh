#!/bin/bash
B=http://localhost:8001/api
T=$(curl -s -X POST $B/auth/login -H "Content-Type: application/json" -d '{"username":"owner","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
H=(-H "Authorization: Bearer $T" -H "Content-Type: application/json")
prod(){ curl -s $B/products "${H[@]}" | python3 -c "import sys,json;p=[x for x in json.load(sys.stdin) if x['name']=='$1'][0];print(p['id'],'kg=',p['stock_kg'],'ekor=',p['stock_ekor'],'pcs=',p['stock_pcs'])"; }
SUP=$(curl -s $B/suppliers "${H[@]}" | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')
FID=$(prod 'Ayam Fillet' | cut -d' ' -f1)
echo "AWAL     : $(prod 'Ayam Fillet')"
R=$(curl -s -X POST $B/purchases "${H[@]}" -d "{\"supplier_id\":\"$SUP\",\"items\":[{\"product_id\":\"$FID\",\"ekor\":5,\"pcs_after\":10,\"total_weight\":4,\"total_price\":200000}],\"paid\":200000}")
PID=$(echo "$R" | python3 -c 'import sys,json;d=json.load(sys.stdin);i=d["items"][0];print(d["id"]);print("  item:",{k:i[k] for k in ("qty_unit","pcs_supplier","pcs","avg_weight","buy_price_kg","buy_price_pcs","subtotal")},"| total_modal",d["total_modal"],"total_pcs",d["total_pcs"],file=sys.stderr)')
echo "BELI 5->10: $(prod 'Ayam Fillet')   <- kg +4, pcs +10"
curl -s -o /dev/null -w "KOREKSI (5->8 pcs, 3 kg) HTTP %{http_code}\n" -X PUT $B/purchases/$PID "${H[@]}" -d "{\"supplier_id\":\"$SUP\",\"items\":[{\"product_id\":\"$FID\",\"ekor\":5,\"pcs_after\":8,\"total_weight\":3,\"total_price\":150000}],\"paid\":150000}"
echo "KOREKSI  : $(prod 'Ayam Fillet')   <- kg +3, pcs +8 dari awal"
# tanpa pcs_after -> fallback = jumlah supplier
curl -s -o /dev/null -w "KOREKSI (tanpa pcs_after, 5 pcs) HTTP %{http_code}\n" -X PUT $B/purchases/$PID "${H[@]}" -d "{\"supplier_id\":\"$SUP\",\"items\":[{\"product_id\":\"$FID\",\"ekor\":5,\"total_weight\":3,\"total_price\":150000}],\"paid\":150000}"
echo "FALLBACK : $(prod 'Ayam Fillet')   <- kg +3, pcs +5 dari awal"
curl -s -o /dev/null -w "HAPUS HTTP %{http_code}\n" -X DELETE $B/purchases/$PID "${H[@]}"
echo "HAPUS    : $(prod 'Ayam Fillet')   <- kembali ke awal"
