
import os
import socket
from getpass import getpass
from flask import Flask, render_template_string, jsonify, request
import routeros_api

app = Flask(__name__)

CONFIG = {
    "host": os.getenv("MIKROTIK_HOST", "10.0.0.1"),
    "username": os.getenv("MIKROTIK_USER", "admin"),
    "password": os.getenv("MIKROTIK_PASSWORD", ""),
    "port": int(os.getenv("MIKROTIK_PORT", "8728")),
}

HTML = r"""
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>لوحة MikroTik</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--muted:#9aa4b2;--ok:#3ac46d;--bad:#ef5350;--line:#282d38;--txt:#f5f7fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:system-ui,-apple-system,"Segoe UI",Tahoma,Arial}
header{padding:18px 16px;background:#11141a;position:sticky;top:0;border-bottom:1px solid var(--line);z-index:5}
h1{font-size:20px;margin:0}.sub{color:var(--muted);font-size:13px;margin-top:5px}
main{padding:14px;max-width:900px;margin:auto}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.card h3{margin:0 0 8px;font-size:14px;color:var(--muted)}.value{font-size:22px;font-weight:700}
.full{grid-column:1/-1}.ok{color:var(--ok)}.bad{color:var(--bad)}button{width:100%;padding:13px;border:0;border-radius:12px;background:#2d7ff9;color:white;font-weight:700;font-size:15px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:9px;border-bottom:1px solid var(--line);text-align:right}
pre{white-space:pre-wrap;word-break:break-word;color:#d8dee9;font-size:12px}
#status{margin:10px 0;color:var(--muted)}
@media(min-width:650px){.grid{grid-template-columns:repeat(4,1fr)}}
</style>
</head>
<body>
<header>
<h1>لوحة MikroTik المحمولة</h1>
<div class="sub">قراءة فقط — لا تنفذ أي تعديل على الراوتر</div>
</header>
<main>
<button onclick="loadData()">تحديث البيانات</button>
<div id="status">اضغط تحديث البيانات</div>

<div class="grid">
  <div class="card"><h3>حالة الاتصال</h3><div id="connection" class="value">—</div></div>
  <div class="card"><h3>اسم الراوتر</h3><div id="identity" class="value">—</div></div>
  <div class="card"><h3>المعالج CPU</h3><div id="cpu" class="value">—</div></div>
  <div class="card"><h3>مستخدمو Hotspot</h3><div id="hotspot" class="value">—</div></div>
  <div class="card full"><h3>معلومات النظام</h3><pre id="system">—</pre></div>
  <div class="card full"><h3>الواجهات</h3><div style="overflow:auto"><table><thead><tr><th>الاسم</th><th>النوع</th><th>الحالة</th><th>Rx</th><th>Tx</th></tr></thead><tbody id="interfaces"></tbody></table></div></div>
  <div class="card full"><h3>آخر السجلات</h3><pre id="logs">—</pre></div>
  <div class="card full"><h3>تحليل سريع</h3><pre id="analysis">—</pre></div>
</div>
</main>
<script>
function fmtBytes(v){
  let n=Number(v||0), u=['B','KB','MB','GB','TB'],i=0;
  while(n>=1024&&i<u.length-1){n/=1024;i++}
  return n.toFixed(i?1:0)+' '+u[i]
}
async function loadData(){
  const s=document.getElementById('status'); s.textContent='جارٍ الاتصال...';
  try{
    const r=await fetch('/api/status'); const d=await r.json();
    if(!r.ok) throw new Error(d.error||'فشل الاتصال');
    document.getElementById('connection').textContent='متصل';
    document.getElementById('connection').className='value ok';
    document.getElementById('identity').textContent=d.identity||'غير معروف';
    document.getElementById('cpu').textContent=(d.resource['cpu-load']||0)+'%';
    document.getElementById('hotspot').textContent=d.hotspot_active_count;
    document.getElementById('system').textContent=
      'الإصدار: '+(d.resource.version||'—')+'\n'+
      'الجهاز: '+(d.resource['board-name']||'—')+'\n'+
      'مدة التشغيل: '+(d.resource.uptime||'—')+'\n'+
      'الذاكرة الحرة: '+fmtBytes(d.resource['free-memory'])+'\n'+
      'الذاكرة الكلية: '+fmtBytes(d.resource['total-memory']);
    const tbody=document.getElementById('interfaces'); tbody.innerHTML='';
    d.interfaces.forEach(x=>{
      const tr=document.createElement('tr');
      tr.innerHTML='<td>'+esc(x.name||'')+'</td><td>'+esc(x.type||'')+'</td><td class="'+(x.running?'ok':'bad')+'">'+(x.running?'تعمل':'متوقفة')+'</td><td>'+fmtBytes(x['rx-byte'])+'</td><td>'+fmtBytes(x['tx-byte'])+'</td>';
      tbody.appendChild(tr);
    });
    document.getElementById('logs').textContent=d.logs.map(x=>(x.time||'')+' | '+(x.topics||'')+' | '+(x.message||'')).join('\n')||'لا توجد سجلات';
    document.getElementById('analysis').textContent=d.analysis.join('\n');
    s.textContent='آخر تحديث: '+new Date().toLocaleString('ar');
  }catch(e){
    document.getElementById('connection').textContent='غير متصل';
    document.getElementById('connection').className='value bad';
    s.textContent='الخطأ: '+e.message;
  }
}
function esc(v){return String(v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
loadData();
</script>
</body>
</html>
"""

def connect():
    pool = routeros_api.RouterOsApiPool(
        CONFIG["host"],
        username=CONFIG["username"],
        password=CONFIG["password"],
        port=CONFIG["port"],
        plaintext_login=True,
        use_ssl=False,
        ssl_verify=False,
        ssl_verify_hostname=False,
    )
    return pool, pool.get_api()

def safe_get(api, path):
    try:
        return api.get_resource(path).get()
    except Exception:
        return []

def quick_analysis(resource, interfaces, hotspot_count, logs):
    notes = []
    try:
        cpu = int(resource.get("cpu-load", 0))
    except Exception:
        cpu = 0
    if cpu >= 85:
        notes.append("⚠️ استخدام المعالج مرتفع جدًا.")
    elif cpu >= 60:
        notes.append("تنبيه: استخدام المعالج مرتفع نسبيًا.")
    else:
        notes.append("✅ استخدام المعالج طبيعي.")

    down = [x.get("name", "غير معروف") for x in interfaces if str(x.get("running", "false")).lower() != "true"]
    if down:
        notes.append("واجهات متوقفة: " + "، ".join(down[:12]))
    else:
        notes.append("✅ جميع الواجهات المعروضة تعمل.")

    notes.append(f"عدد مستخدمي Hotspot المتصلين: {hotspot_count}")
    login_logs = [x for x in logs if "logged in" in str(x.get("message", "")).lower()]
    if login_logs:
        notes.append(f"تم العثور على {len(login_logs)} سجل دخول ضمن آخر السجلات.")
    return notes

@app.get("/")
def index():
    return render_template_string(HTML)

@app.get("/api/status")
def status():
    pool = None
    try:
        pool, api = connect()
        resource_list = safe_get(api, "/system/resource")
        identity_list = safe_get(api, "/system/identity")
        interfaces = safe_get(api, "/interface")
        hotspot_active = safe_get(api, "/ip/hotspot/active")
        logs = safe_get(api, "/log")
        resource = resource_list[0] if resource_list else {}
        identity = identity_list[0].get("name", "غير معروف") if identity_list else "غير معروف"

        # تقليل البيانات المعروضة
        interfaces = interfaces[:80]
        logs = logs[-40:]
        return jsonify({
            "identity": identity,
            "resource": resource,
            "interfaces": interfaces,
            "hotspot_active_count": len(hotspot_active),
            "logs": logs,
            "analysis": quick_analysis(resource, interfaces, len(hotspot_active), logs),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if pool:
                pool.disconnect()
        except Exception:
            pass

def ask_config():
    print("\nإعداد الاتصال بالـ MikroTik")
    host = input(f"عنوان الراوتر [{CONFIG['host']}]: ").strip() or CONFIG["host"]
    username = input(f"اسم المستخدم [{CONFIG['username']}]: ").strip() or CONFIG["username"]
    password = getpass("كلمة المرور (لن تظهر أثناء الكتابة): ")
    CONFIG.update({"host": host, "username": username, "password": password})

if __name__ == "__main__":
    ask_config()
    print("\nافتح هذا العنوان في متصفح الهاتف:")
    print("http://127.0.0.1:8080")
    print("\nلإيقاف البرنامج اضغط CTRL ثم C داخل Termux.")
    app.run(host="127.0.0.1", port=8080, debug=False)
