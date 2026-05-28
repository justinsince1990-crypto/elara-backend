js="""<script>
async function initWebPush(){
 const b=document.getElementById('enable-push-btn');
 try{
  const reg=await navigator.serviceWorker.register('/service-worker.js');
  const p=await Notification.requestPermission();
  if(p==='granted'){
   const res=await fetch('/push/public_key');
   const key=await res.text();
   const pad='='.repeat((4-key.length%4)%4);
   const b64=(key+pad).replace(/-/g,'+').replace(/_/g,'/');
   const raw=window.atob(b64);
   const arr=new Uint8Array(raw.length);
   for(let i=0;i<raw.length;++i)arr[i]=raw.charCodeAt(i);
   const sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:arr});
   await fetch('/push_token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:JSON.stringify(sub)})});
   if(b)b.innerHTML='🔔 Bound!';alert('Handshake Successful!');
  }else{alert('Denied by OS.');}
 }catch(e){alert('Err: '+e.message);}
}
async function triggerMemorySync(){
 const b=document.getElementById('sync-memory-btn');
 b.innerHTML='⚙️...';
 try{
  const r=await fetch('/memory/consolidate',{method:'POST'});
  const d=await r.json();
  b.innerHTML=d.ok?'✅ Synced':'❌ Failed';
 }catch(e){b.innerHTML='❌ Err';}
 setTimeout(()=>b.innerHTML='🧠 Sync Memory',3000);
}
</script>"""
with open('/root/elara/chat_ui.html', 'r') as f: h=f.read()
if 'initWebPush()' not in h:
 h=h.replace('</body>', js + '\n</body>')
 with open('/root/elara/chat_ui.html', 'w') as f: f.write(h)
print("2. JavaScript successfully injected!")
