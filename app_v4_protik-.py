import os
import re
from datetime import datetime
from getpass import getpass
from flask import Flask, render_template_string, jsonify, request
import routeros_api

app = Flask(__name__)
CONFIG={"host":os.getenv("MIKROTIK_HOST","10.0.0.1"),"username":os.getenv("MIKROTIK_USER","admin"),"password":os.getenv("MIKROTIK_PASSWORD",""),"port":int(os.getenv("MIKROTIK_PORT","8728"))}

HTML='''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مساعد MikroTik</title><style>body{margin:0;background:#0f1115;color:#f5f7fa;font-family:system-ui,Tahoma}header,main{padding:16px}header{background:#11141a;border-bottom:1px solid #282d38}.card{background:#171a21;border:1px solid #282d38;border-radius:14px;padding:14px;margin:10px 0}.muted{color:#9aa4b2}.ok{color:#3ac46d}.bad{color:#ef5350}.warn{color:#f2b84b}button,input{width:100%;padding:13px;border-radius:12px;margin-top:8px;font-size:15px;box-sizing:border-box}button{border:0;background:#2d7ff9;color:#fff;font-weight:700}button.danger{background:#c62828}button.secondary{background:#404756}input{border:1px solid #282d38;background:#101318;color:#fff}pre{white-space:pre-wrap;word-break:break-word}</style></head><body><header><h2>مساعد MikroTik المحمول</h2><div class="muted">تنفيذ محدود بعد موافقتك</div></header><main><button onclick="loadData()">تحديث البيانات</button><div id="status" class="muted"></div><div class="card"><h3>حالة الراوتر</h3><pre id="info">—</pre></div><div class="card"><h3>حذف الكروت المنتهية بأمان</h3><div class="muted">تعتبر البطاقة منتهية إذا انتهى وقتها، أو استُهلك رصيد البيانات، أو انتهى تاريخ الصلاحية المسجل بواسطة ProTik.</div><button class="secondary" onclick="previewExpired()">معاينة قبل الحذف</button><pre id="preview">لم تتم المعاينة.</pre><input id="confirmText" placeholder="اكتب: احذف المنتهية"><button class="danger" onclick="deleteExpired()">حذف بعد التأكيد</button><div id="result"></div></div><div class="card"><h3>آخر السجلات</h3><pre id="logs">—</pre></div></main><script>
async function loadData(){
const statusEl=document.getElementById('status'),infoEl=document.getElementById('info'),logsEl=document.getElementById('logs');
statusEl.textContent='جارٍ الاتصال...';
try{
let r=await fetch('/api/status'),d=await r.json();
if(!r.ok)throw Error(d.error||'فشل الاتصال');
infoEl.textContent=['متصل ✅','اسم الراوتر: '+d.identity,'CPU: '+(d.resource['cpu-load']||0)+'%','الإصدار: '+(d.resource.version||'—'),'المستخدمون المتصلون: '+d.hotspot_active_count].join('\\n');
logsEl.textContent=d.logs.map(x=>(x.time||'')+' | '+(x.message||'')).join('\\n')||'لا توجد سجلات';
statusEl.textContent='تم التحديث';
}catch(e){statusEl.textContent='الخطأ: '+e.message}
}
async function previewExpired(){
const previewEl=document.getElementById('preview');
previewEl.textContent='جارٍ الفحص...';
try{
let r=await fetch('/api/expired-users'),d=await r.json();
if(!r.ok)throw Error(d.error||'فشل الفحص');
previewEl.textContent=d.users.length?(['العدد: '+d.users.length].concat(d.users.map((u,i)=>(i+1)+'. '+(u.name||'بدون اسم')+' | السبب: '+(u.reasons||[]).join(' + ')+' | الصلاحية: '+(u.expiry_date||'—')+' | '+(u.comment||'—'))).join('\\n')):'لا توجد كروت منتهية قابلة للحذف.';
}catch(e){previewEl.textContent='الخطأ: '+e.message}
}
async function deleteExpired(){
const confirmEl=document.getElementById('confirmText'),resultEl=document.getElementById('result');
let c=confirmEl.value.trim();
if(c!=='احذف المنتهية'){resultEl.textContent='اكتب العبارة المطلوبة حرفيًا.';resultEl.className='warn';return}
if(!confirm('سيتم حذف جميع كروت ProTik التي انتهى وقتها أو رصيدها أو صلاحيتها. متابعة؟'))return;
try{
let r=await fetch('/api/delete-expired',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:'احذف المنتهية'})}),d=await r.json();
if(!r.ok)throw Error(d.error||'فشل الحذف');
resultEl.textContent='تم حذف '+d.deleted_count+' كرت منتهي.'+(d.skipped_count?' وتعذر حذف '+d.skipped_count+'.':'');
resultEl.className='ok';
confirmEl.value='';
previewExpired();
loadData();
}catch(e){resultEl.textContent='الخطأ: '+e.message;resultEl.className='bad'}
}
loadData();</script></body></html>'''

def connect():
    pool=routeros_api.RouterOsApiPool(CONFIG['host'],username=CONFIG['username'],password=CONFIG['password'],port=CONFIG['port'],plaintext_login=True,use_ssl=False,ssl_verify=False,ssl_verify_hostname=False)
    return pool,pool.get_api()

def safe_get(api,path):
    try:return api.get_resource(path).get()
    except Exception:return []

@app.get('/')
def index(): return render_template_string(HTML)

@app.get('/api/status')
def status():
    pool=None
    try:
        pool,api=connect(); res=safe_get(api,'/system/resource'); ident=safe_get(api,'/system/identity'); active=safe_get(api,'/ip/hotspot/active'); logs=safe_get(api,'/log')
        return jsonify({'identity':ident[0].get('name','غير معروف') if ident else 'غير معروف','resource':res[0] if res else {},'hotspot_active_count':len(active),'logs':logs[-40:]})
    except Exception as e:return jsonify({'error':str(e)}),500
    finally:
        try:
            if pool: pool.disconnect()
        except Exception: pass


def parse_router_time(value):
    if not value:
        return 0
    s = str(value).strip().lower()
    total = 0
    m = re.search(r"(\d+)w", s)
    if m:
        total += int(m.group(1)) * 7 * 86400
    m = re.search(r"(\d+)d", s)
    if m:
        total += int(m.group(1)) * 86400
    tail = re.search(r"(\d+):(\d+):(\d+)$", s)
    if tail:
        total += int(tail.group(1)) * 3600 + int(tail.group(2)) * 60 + int(tail.group(3))
    elif s.isdigit():
        total += int(s)
    return total

def parse_router_bytes(value):
    if value is None or value == "":
        return 0
    s = str(value).strip().upper()
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGTP]?)", s)
    if not m:
        try:
            return int(float(s))
        except Exception:
            return 0
    number = float(m.group(1))
    unit = m.group(2)
    multipliers = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}
    return int(number * multipliers[unit])

def protik_expiry_date(user):
    combined = " ".join(str(user.get(k, "")) for k in ("comment", "email", "name"))
    match = re.search(r"(?:C:|EXP:|EXPIRE:)?\s*(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", combined, re.I)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
    except ValueError:
        return None

def classify_expired_user(user):
    reasons = []

    uptime = parse_router_time(user.get("uptime"))
    limit_uptime = parse_router_time(user.get("limit-uptime"))
    if limit_uptime > 0 and uptime >= limit_uptime:
        reasons.append("انتهاء الوقت")

    used_bytes = parse_router_bytes(user.get("bytes-in")) + parse_router_bytes(user.get("bytes-out"))
    limit_total = parse_router_bytes(user.get("limit-bytes-total"))
    if limit_total > 0 and used_bytes >= limit_total:
        reasons.append("انتهاء الرصيد")

    expiry = protik_expiry_date(user)
    if expiry is not None and expiry < datetime.now().date():
        reasons.append("انتهاء الصلاحية")

    return reasons, {
        ".id": user.get(".id"),
        "name": user.get("name", ""),
        "profile": user.get("profile", ""),
        "comment": user.get("comment", ""),
        "uptime": user.get("uptime", "0s"),
        "limit_uptime": user.get("limit-uptime", "0s"),
        "used_bytes": used_bytes,
        "limit_bytes_total": limit_total,
        "expiry_date": expiry.isoformat() if expiry else "",
    }

@app.get('/api/expired-users')
def expired_users():
    pool = None
    try:
        pool, api = connect()
        users = api.get_resource('/ip/hotspot/user').get()
        expired = []
        for user in users:
            reasons, item = classify_expired_user(user)
            if reasons:
                item["reasons"] = reasons
                expired.append(item)
        return jsonify({"users": expired, "count": len(expired)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if pool:
                pool.disconnect()
        except Exception:
            pass

@app.post('/api/delete-expired')
def delete_expired():
    data = request.get_json(silent=True) or {}
    if data.get('confirm') != 'احذف المنتهية':
        return jsonify({"error": "التأكيد غير صحيح"}), 400

    pool = None
    try:
        pool, api = connect()
        user_resource = api.get_resource('/ip/hotspot/user')
        active_resource = api.get_resource('/ip/hotspot/active')
        users = user_resource.get()
        deleted = []
        skipped = []

        for user in users:
            reasons, item = classify_expired_user(user)
            if not reasons:
                continue

            username = user.get("name", "")
            user_id = user.get(".id")

            try:
                for session in active_resource.get(user=username):
                    sid = session.get(".id")
                    if sid:
                        active_resource.remove(id=sid)
            except Exception:
                pass

            try:
                if user_id:
                    user_resource.remove(id=user_id)
                    deleted.append({"name": username, "reasons": reasons})
            except Exception as exc:
                skipped.append({"name": username, "error": str(exc)})

        return jsonify({
            "deleted_count": len(deleted),
            "deleted": deleted,
            "skipped_count": len(skipped),
            "skipped": skipped,
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
    print('\nإعداد الاتصال بالـ MikroTik')
    host=input(f"عنوان الراوتر [{CONFIG['host']}]: ").strip() or CONFIG['host']
    username=input(f"اسم المستخدم [{CONFIG['username']}]: ").strip() or CONFIG['username']
    password=getpass('كلمة المرور (لن تظهر أثناء الكتابة): ')
    CONFIG.update({'host':host,'username':username,'password':password})

if __name__=='__main__':
    ask_config(); print('\nافتح في المتصفح:\nhttp://127.0.0.1:8080'); app.run(host='127.0.0.1',port=8080,debug=False)
