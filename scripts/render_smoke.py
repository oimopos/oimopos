import subprocess, secrets, os, time, urllib.request, json
suffix=secrets.token_hex(4); network='oimo-check-'+suffix; db=network+'-db'; web=network+'-web'
def run(args,**kwargs): return subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,**kwargs)
password=secrets.token_hex(24)
env={**os.environ,'POSTGRES_PASSWORD':password,'DATABASE_URL':f'postgresql://postgres:{password}@{db}:5432/postgres','EMPLOYEE_PIN_KEY':secrets.token_hex(32),'PLATFORM_INITIAL_PASSWORD':secrets.token_hex(24),'SESSION_COOKIE_SECURE':'true','RENDER_EXTERNAL_URL':'https://oimo-check.example'}
try:
 run(['docker','network','create',network])
 run(['docker','run','-d','--name',db,'--network',network,'-e','POSTGRES_PASSWORD','postgres:17-alpine'],env=env)
 for _ in range(40):
  if subprocess.run(['docker','exec',db,'pg_isready','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0: break
  time.sleep(1)
 for _ in range(2):
  run(['docker','run','--rm','--network',network,'-e','DATABASE_URL','oimo-render-check','python','/app/render_migrate.py'],env=env)
 print('PASS fresh database + repeat migrations')
 args=['docker','run','-d','--name',web,'--network',network,'-p','127.0.0.1:18080:10000']
 for key in ['DATABASE_URL','EMPLOYEE_PIN_KEY','PLATFORM_INITIAL_PASSWORD','SESSION_COOKIE_SECURE','RENDER_EXTERNAL_URL']: args+=['-e',key]
 run(args+['oimo-render-check'],env=env)
 for _ in range(40):
  try:
   with urllib.request.urlopen('http://127.0.0.1:18080/health') as r: assert json.load(r)['status']=='ok'
   break
  except Exception: time.sleep(1)
 else: raise RuntimeError('health failed')
 for path in ['/','/login','/admin','/pos','/platform','/login.html','/admin.html','/index.html','/platform.html','/oimo.css','/app.js']:
  with urllib.request.urlopen('http://127.0.0.1:18080'+path) as r: assert r.status==200
 for path in ['/.env','/database/init/002_seed.sql','/tests/pos-ui-smoke.html','/app/main.py']:
  try: urllib.request.urlopen('http://127.0.0.1:18080'+path); raise AssertionError(path)
  except urllib.error.HTTPError as e: assert e.code==404
 payload=json.dumps({'login':'platform','password':env['PLATFORM_INITIAL_PASSWORD']}).encode()
 request=urllib.request.Request('http://127.0.0.1:18080/api/v1/auth/login',data=payload,headers={'Content-Type':'application/json','Origin':env['RENDER_EXTERNAL_URL']})
 with urllib.request.urlopen(request) as r:
  assert r.status==200
  assert 'Secure' in r.headers.get('Set-Cookie','')
  cookie=r.headers['Set-Cookie'].split(';')[0]
 headers={'Content-Type':'application/json','Origin':env['RENDER_EXTERNAL_URL'],'Cookie':cookie}
 def api(path, data=None, method=None):
  request=urllib.request.Request('http://127.0.0.1:18080/api/v1'+path, data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
  with urllib.request.urlopen(request) as response:return json.load(response)
 initial=api('/platform/tenants')
 created=[]
 owner_passwords=[]
 for index in range(2):
  owner_passwords.append(secrets.token_hex(16))
  tenant=api('/platform/tenants',{'name':'Demo '+str(index),'slug':'demo-'+str(index),'owner_name':'Demo Owner','email':f'demo{index}@example.com','phone':'+996555123456','owner_password':owner_passwords[-1],'service_modes':['counter'],'location_name':'Demo','location_address':'Demo street','register_password':secrets.token_hex(16)})
  created.append(tenant['id'])
 listed=api('/platform/tenants')
 assert all(any(row['id']==identifier for row in listed) for identifier in created)
 assert len(listed)==len(initial)+2
 print('PASS fresh tenant list and two created accounts remain visible')
 owner_request=urllib.request.Request('http://127.0.0.1:18080/api/v1/auth/login',data=json.dumps({'login':'demo0@example.com','password':owner_passwords[0]}).encode(),headers={'Content-Type':'application/json','Origin':env['RENDER_EXTERNAL_URL']})
 with urllib.request.urlopen(owner_request) as response: owner_cookie=response.headers['Set-Cookie'].split(';')[0]
 platform_cookie=headers['Cookie']
 headers['Cookie']=owner_cookie
 try:
  api('/platform/tenants/'+created[1], {'confirmation_name':'Demo 1'}, 'DELETE')
  raise AssertionError('company owner allowed to delete tenant')
 except urllib.error.HTTPError as error: assert error.code==403
 headers['Cookie']=platform_cookie
 try:
  api('/platform/tenants/'+created[0], {'confirmation_name':'wrong'}, 'DELETE')
  raise AssertionError('wrong confirmation accepted')
 except urllib.error.HTTPError as error: assert error.code==400
 assert len(api('/platform/tenants'))==len(listed)
 result=api('/platform/tenants/'+created[0], {'confirmation_name':'Demo 0'}, 'DELETE')
 assert result['deleted']
 remaining=api('/platform/tenants')
 assert created[0] not in [row['id'] for row in remaining]
 assert created[1] in [row['id'] for row in remaining]
 assert len(remaining)==len(listed)-1
 counts=run(['docker','exec',db,'psql','-U','postgres','-Atc',
  "SELECT count(*) FROM auth_users WHERE tenant_id = '"+created[0]+"'"]).stdout.strip()
 assert counts=='0'
 assert any(event['action']=='tenant.delete' for event in api('/platform/events'))
 headers['Cookie']=owner_cookie
 try:
  api('/auth/me')
  raise AssertionError('deleted session still valid')
 except urllib.error.HTTPError as error: assert error.code==401
 headers['Cookie']=platform_cookie
 print('PASS deletion confirmation, complete account removal, second tenant isolation and audit')
 print('PASS startup, health, frontend, private files not served, login and Secure cookie')
except subprocess.CalledProcessError as e:
 print(e.stderr.replace(password,'[redacted]')); raise SystemExit(1)
finally:
 for name in [web,db]: subprocess.run(['docker','rm','-f','-v',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['docker','network','rm',network],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
