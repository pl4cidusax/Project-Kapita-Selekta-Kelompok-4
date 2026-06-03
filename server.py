#!/usr/bin/env python3
"""
Water Monitoring IoT - SERVER
=============================
Menerima data dari ESP32 (client) lewat HTTP POST (JSON),
menyimpannya ke SQLite, dan menyajikan dashboard + API sederhana.

Jalankan:  python server.py
Lalu buka alamat yang dicetak di terminal (mis. http://192.168.1.100:5000)

Dependensi:  pip install flask
"""

import socket
import sqlite3
from datetime import datetime

from flask import Flask, request, jsonify

DB_PATH = "water_data.db"
PORT = 5000

app = Flask(__name__)


# ---------------------------------------------------------------- database
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ts               TEXT    NOT NULL,
            device_id        TEXT,
            distance_cm      REAL,
            water_level_cm   REAL,
            water_level_pct  REAL,
            water_analog_raw INTEGER,
            water_analog_pct REAL,
            ldr_raw          INTEGER,
            ldr_pct          REAL,
            ldr_dark         INTEGER,
            uptime_ms        INTEGER
        )
        """
    )
    con.commit()
    con.close()


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ------------------------------------------------------------------- routes
@app.route("/api/data", methods=["POST"])
def receive():
    """Endpoint yang dipanggil ESP32. Menerima JSON pembacaan sensor."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"ok": False, "error": "JSON tidak valid"}), 400

    con = get_db()
    con.execute(
        """
        INSERT INTO readings
            (ts, device_id, distance_cm, water_level_cm, water_level_pct,
             water_analog_raw, water_analog_pct, ldr_raw, ldr_pct,
             ldr_dark, uptime_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            data.get("device_id"),
            data.get("distance_cm"),
            data.get("water_level_cm"),
            data.get("water_level_pct"),
            data.get("water_analog_raw"),
            data.get("water_analog_pct"),
            data.get("ldr_raw"),
            data.get("ldr_pct"),
            1 if data.get("ldr_dark") else 0,
            data.get("uptime_ms"),
        ),
    )
    con.commit()
    con.close()

    print(
        f"[{datetime.now():%H:%M:%S}] {data.get('device_id', '?')}  "
        f"tinggi_air={data.get('water_level_cm')}cm  "
        f"water_raw={data.get('water_analog_raw')}  "
        f"ldr={data.get('ldr_raw')}  "
        f"{'GELAP' if data.get('ldr_dark') else 'terang'}"
    )
    return jsonify({"ok": True})


@app.route("/api/latest")
def latest():
    con = get_db()
    row = con.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    return jsonify(dict(row) if row else {})


@app.route("/api/history")
def history():
    limit = request.args.get("limit", 50, type=int)
    con = get_db()
    rows = con.execute(
        "SELECT * FROM readings ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


@app.route("/")
def dashboard():
    # Dikembalikan sebagai string biasa -> Flask kirim sebagai text/html
    # (tanpa proses Jinja, supaya kurung kurawal di JS/CSS aman).
    return DASHBOARD


# --------------------------------------------------------------- dashboard
DASHBOARD = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Water Monitoring</title>
<style>
  :root{--bg:#0f1620;--card:#1a2533;--ink:#e6edf3;--muted:#7d8da1;--accent:#3fb6ff;}
  *{box-sizing:border-box;}
  body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink);}
  header{padding:20px;border-bottom:1px solid #243042;}
  h1{margin:0;font-size:18px;}
  .sub{color:var(--muted);font-size:13px;margin-top:4px;}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;padding:20px;}
  .card{background:var(--card);border:1px solid #243042;border-radius:12px;padding:16px;}
  .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em;}
  .value{font-size:28px;font-weight:600;margin-top:6px;}
  .unit{font-size:14px;color:var(--muted);font-weight:400;}
  .bar{height:8px;background:#243042;border-radius:6px;margin-top:10px;overflow:hidden;}
  .bar>div{height:100%;background:var(--accent);width:0;transition:width .4s;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #243042;white-space:nowrap;}
  th{color:var(--muted);font-weight:500;}
  .wrap{padding:0 20px 30px;overflow-x:auto;}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;}
  .on{background:#ffd23f;}.off{background:#3a4658;}
</style>
</head>
<body>
<header>
  <h1>&#128167; Water Monitoring Dashboard</h1>
  <div class="sub" id="meta">Menunggu data dari ESP32&hellip;</div>
</header>
<div class="grid" id="cards"></div>
<div class="wrap">
  <h3 style="margin:0 0 10px;font-size:14px;color:var(--muted)">Riwayat terakhir</h3>
  <table>
    <thead><tr>
      <th>Waktu</th><th>Jarak</th><th>Tinggi air</th><th>%</th>
      <th>Water raw</th><th>LDR</th><th>Cahaya</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<script>
function fmt(v,dp){ if(dp===undefined)dp=1; return (v===null||v===undefined)?'':Number(v).toFixed(dp); }
function card(label,value,unit,pct){
  var bar = (pct===null||pct===undefined) ? '' :
    '<div class="bar"><div style="width:'+Math.max(0,Math.min(100,pct))+'%"></div></div>';
  return '<div class="card"><div class="label">'+label+'</div>'+
         '<div class="value">'+value+'<span class="unit"> '+(unit||'')+'</span></div>'+bar+'</div>';
}
async function refresh(){
  try{
    var d = await (await fetch('/api/latest')).json();
    if(!d || !d.ts){ return; }
    document.getElementById('meta').textContent =
      (d.device_id||'device') + ' \u00b7 update ' + d.ts;
    var dist=d.distance_cm, lvl=d.water_level_cm, lvlp=d.water_level_pct;
    document.getElementById('cards').innerHTML =
      card('Tinggi air', (lvl!=null&&lvl>=0)?lvl.toFixed(1):'\u2014','cm',(lvlp!=null&&lvlp>=0)?lvlp:null) +
      card('Level ultrasonik',(lvlp!=null&&lvlp>=0)?lvlp.toFixed(0):'\u2014','%',(lvlp!=null&&lvlp>=0)?lvlp:null) +
      card('Jarak sensor',(dist!=null&&dist>=0)?dist.toFixed(1):'\u2014','cm',null) +
      card('Water sensor', d.water_analog_raw!=null?d.water_analog_raw:'\u2014','raw', d.water_analog_pct) +
      card('LDR (cahaya)', d.ldr_raw!=null?d.ldr_raw:'\u2014','raw', d.ldr_pct) +
      card('Kondisi', d.ldr_dark?'Gelap':'Terang','',null);
    var h = await (await fetch('/api/history?limit=20')).json();
    document.getElementById('rows').innerHTML = h.map(function(x){
      return '<tr>'+
        '<td>'+((x.ts||'').replace('T',' '))+'</td>'+
        '<td>'+fmt(x.distance_cm)+'</td>'+
        '<td>'+fmt(x.water_level_cm)+'</td>'+
        '<td>'+fmt(x.water_level_pct,0)+'</td>'+
        '<td>'+(x.water_analog_raw!=null?x.water_analog_raw:'')+'</td>'+
        '<td>'+(x.ldr_raw!=null?x.ldr_raw:'')+'</td>'+
        '<td><span class="dot '+(x.ldr_dark?'off':'on')+'"></span>'+(x.ldr_dark?'gelap':'terang')+'</td>'+
      '</tr>';
    }).join('');
  }catch(e){ console.error(e); }
}
refresh(); setInterval(refresh, 3000);
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ helper
def local_ip():
    """Tebak alamat IP LAN komputer ini (untuk dimasukkan ke kode ESP32)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    init_db()
    ip = local_ip()
    print("=" * 60)
    print(" Water Monitoring Server berjalan")
    print(f"   Dashboard       : http://{ip}:{PORT}")
    print(f"   Endpoint ESP32  : http://{ip}:{PORT}/api/data   <-- isi ke .ino")
    print("   (Tekan Ctrl+C untuk berhenti)")
    print("=" * 60)
    # host=0.0.0.0 supaya bisa diakses ESP32 dari jaringan WiFi yang sama
    app.run(host="0.0.0.0", port=PORT, debug=False)
