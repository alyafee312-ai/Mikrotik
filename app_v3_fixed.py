import os
from getpass import getpass
from flask import Flask, render_template_string, jsonify, request
import routeros_api

app = Flask(__name__)
CONFIG={"host":os.getenv("MIKROTIK_HOST","10.0.0.1"),"username":os.getenv("MIKROTIK_USER","admin"),"password":os.getenv("MIKROTIK_PASSWORD",""),"port":int(os.getenv("MIKROTIK_PORT","8728"))}

HTML='''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مساعد MikroTik</title><style>body{margin:0;background:#0f1115;color:#f5f7fa;font-family:system-ui,Tahoma}header,main{padding:16px}header{background:#11141a;border-bottom:1px solid #282d38}.card{background:#171a21;border:1px solid #282d38;border-radius:14px;padding:14px;margin:10px 0}.muted{color:#9aa4b2}.ok{color:#3ac46d}.bad{color:#ef5350}.warn{color:#f2b84b}button,input{width:100%;padding:13px;border-radius:12px;margin-top:8px;font-size:15px;box-sizing:border-box}button{border:0;background:#2d7ff9;color:#fff;font-weight:700}button.danger{background:#c62828}button.secondary{background:#404756}input{border:1px solid #282d38;background:#101318;color:#fff}pre{white-space:pre-wrap;word-break:break-word}</style></head><body><header><h2>مساعد MikroTik المحمول</h2><div class="muted">تنفيذ محدود بعد موافقتك</div></header><main><button onclick="loadData()">تحديث البيانات</button><div id="status" class="muted"></div><div class="card"><h3>حالة الراوتر</h3><pre id="info">—</pre></div><div class="card"><h3>حذف الكروت المنتهية بأمان</h3><div class="muted">هذه النسخة تعتبر المنتهية هي مستخدمي Hotspot المعطّلين فقط (disabled=yes)، ولن تحذف النشطين.</div><button class="secondary" onclick="previewExpired()">معاينة قبل الحذف</button><pre id="preview">لم تتم المعاينة.</pre><input id="confirmText" placeholder="اكتب: احذف المنتهية"><button class="danger" onclick="deleteExpired()">حذف بعد التأكيد</button><div id="result"></div></div><div class="card"><h3>آخر السجلات</h3><pre id="logs">—</pre></div></main><script>
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
previewEl.textContent=d.users.length?(['العدد: '+d.users.length].concat(d.users.map((u,i)=>(i+1)+'. '+(u.name||'بدون اسم')+' | '+(u.profile||'—')+' | '+(u.comment||'—'))).join('\\n')):'لا توجد كروت معطلة قابلة للحذف.';
}catch(e){previewEl.textContent='الخطأ: '+e.message}
}
async function deleteExpired(){
const confirmEl=document.getElementById('confirmText'),resultEl=document.getElementById('result');
let c=confirmEl.value.trim();
if(c!=='احذف المنتهية'){resultEl.textContent='اكتب العبارة المطلوبة حرفيًا.';resultEl.className='warn';return}
if(!confirm('سيتم حذف جميع مستخدمي Hotspot المعطّلين فقط. متابعة؟'))return;
try{
let r=await fetch('/api/delete-expired',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:'احذف المنتهية'})}),d=await r.json();
if(!r.ok)throw Error(d.error||'فشل الحذف');
resultEl.textContent='تم حذف '+d.deleted_count+' كرت/مستخدم معطّل.';
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

@app.get('/api/expired-users')
def expired_users():
    pool=None
    try:
        pool,api=connect(); users=api.get_resource('/ip/hotspot/user').get(disabled='true')
        return jsonify({'users':[{'id':u.get('.id'),'name':u.get('name',''),'profile':u.get('profile',''),'comment':u.get('comment','')} for u in users]})
    except Exception as e:return jsonify({'error':str(e)}),500
    finally:
        try:
            if pool: pool.disconnect()
        except Exception: pass

@app.post('/api/delete-expired')
def delete_expired():
    data=request.get_json(silent=True) or {}
    if data.get('confirm')!='احذف المنتهية': return jsonify({'error':'التأكيد غير صحيح'}),400
    pool=None
    try:
        pool,api=connect(); resource=api.get_resource('/ip/hotspot/user'); users=resource.get(disabled='true'); deleted=0
        for u in users:
            uid=u.get('.id')
            if uid: resource.remove(id=uid); deleted+=1
        return jsonify({'deleted_count':deleted})
    except Exception as e:return jsonify({'error':str(e)}),500
    finally:
        try:
            if pool: pool.disconnect()
        except Exception: pass

def ask_config():
    print('\nإعداد الاتصال بالـ MikroTik')
    host=input(f"عنوان الراوتر [{CONFIG['host']}]: ").strip() or CONFIG['host']
    username=input(f"اسم المستخدم [{CONFIG['username']}]: ").strip() or CONFIG['username']
    password=getpass('كلمة المرور (لن تظهر أثناء الكتابة): ')
    CONFIG.update({'host':host,'username':username,'password':password})

if __name__=='__main__':
    ask_config(); print('\nافتح في المتصفح:\nhttp://127.0.0.1:8080'); app.run(host='127.0.0.1',port=8080,debug=False)
