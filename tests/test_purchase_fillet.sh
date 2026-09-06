#!/bin/bash
B=http://localhost:8001/api
T=$(curl -s -X POST $B/auth/login -H "Content-Type: application/json" -d '{"username":"owner","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
H=(-H "Authorization: Bearer $T" -H "Content-Type: application/json")
prod(){ curl -s $B/products "${H[@]}" | python3 -c "import sys,json;p=[x for x in json.load(sys.stdin) if x['name']=='$1'][0];print(p['id'],p['stock_kg'],p['stock_ekor'],p['stock_pcs'],p.get('units'),p.get('cum_ekor_in',0),p.get('hpp_kg'))"; }
SUP=$(curl -s $B/suppliers "${H[@]}" | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')
echo "SEBELUM  Fillet : $(prod 'Ayam Fillet')"; echo "SEBELUM  Broiler: $(prod 'Ayam Broiler')"
FID=$(prod 'Ayam Fillet' | cut -d' ' -f1); BID=$(prod 'Ayam Broiler' | cut -d' ' -f1)
# 1) Pembelian campuran: 10 ekor Broiler 20 kg Rp 480rb + 5 pcs Fillet 4 kg Rp 200rb
R=$(curl -s -X POST $B/purchases "${H[@]}" -d "{\"supplier_id\":\"$SUP\",\"items\":[{\"product_id\":\"$BID\",\"ekor\":10,\"total_weight\":20,\"total_price\":480000},{\"product_id\":\"$FID\",\"ekor\":5,\"total_weight\":4,\"total_price\":200000}],\"paid\":680000}")
PID=$(echo "$R" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["id"]);print("  doc items:",[(i["name"],i["qty_unit"],i["ekor"],i["pcs"],i["avg_weight"]) for i in d["items"]],"total_ekor",d["total_ekor"],"total_pcs",d["total_pcs"],file=sys.stderr)')
echo "SESUDAH  Fillet : $(prod 'Ayam Fillet')   <- harus kg +4, pcs +5, ekor tetap, units ada pcs"
echo "SESUDAH  Broiler: $(prod 'Ayam Broiler')   <- kg +20, ekor +10, cum_ekor +10"
echo "MOVEMENT fillet:"; curl -s $B/stock-movements "${H[@]}" | python3 -c "import sys,json;[print('  ',m['type'],m.get('qty_kg'),m.get('qty_ekor'),m.get('qty_pcs'),'->',m.get('after_kg'),m.get('after_pcs')) for m in json.load(sys.stdin) if m.get('product_id')=='$FID' and m.get('ref')=='$PID']"
# 2) Koreksi: fillet jadi 3 pcs 2 kg
curl -s -o /dev/null -w "KOREKSI HTTP %{http_code}\n" -X PUT $B/purchases/$PID "${H[@]}" -d "{\"supplier_id\":\"$SUP\",\"items\":[{\"product_id\":\"$BID\",\"ekor\":10,\"total_weight\":20,\"total_price\":480000},{\"product_id\":\"$FID\",\"ekor\":3,\"total_weight\":2,\"total_price\":100000}],\"paid\":580000}"
echo "KOREKSI  Fillet : $(prod 'Ayam Fillet')   <- kg +2, pcs +3 dari awal"
# 3) Hapus
curl -s -o /dev/null -w "HAPUS HTTP %{http_code}\n" -X DELETE $B/purchases/$PID "${H[@]}"
echo "HAPUS    Fillet : $(prod 'Ayam Fillet')   <- kembali ke awal (units pcs tetap)"
echo "HAPUS    Broiler: $(prod 'Ayam Broiler')   <- kembali ke awal"
