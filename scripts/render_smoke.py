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
 print('PASS startup, health, frontend, private files not served, login and Secure cookie')
except subprocess.CalledProcessError as e:
 print(e.stderr.replace(password,'[redacted]')); raise SystemExit(1)
finally:
 for name in [web,db]: subprocess.run(['docker','rm','-f','-v',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['docker','network','rm',network],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
