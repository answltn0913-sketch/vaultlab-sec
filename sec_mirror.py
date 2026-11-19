# 볼트랩 SEC 미러: 볼트랩이 필요하다고 적어 둔 SEC 주소를 받아서 GitHub에 보관해요.
import gzip, hashlib, json, os, re, sys, time, urllib.request, urllib.error

SITE = 'https://vaultlab.kr'
UA = 'VaultLab Research anwltn9341@naver.com'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
MAX = 450          # 한 번에 받을 최대 개수
GAP = 0.13         # SEC 규칙: 1초에 10번 미만
os.makedirs(os.path.join(OUT, 'm'), exist_ok=True)
state_p = os.path.join(OUT, 'state.json')
state = json.load(open(state_p)) if os.path.exists(state_p) else {}

def ttl(u):
    if '/Archives/' in u: return 30 * 86400
    if 'getcurrent' in u: return 15 * 60
    if '/submissions/' in u: return 3600
    if '/frames/' in u or 'company_tickers' in u: return 12 * 3600
    if 'companyconcept' in u or 'companyfacts' in u: return 24 * 3600
    return 3600

tok = os.environ.get('VLST_TOKEN', '').strip()
print('암호 길이:', len(tok), '(32가 맞아요)')
SEED = [{'u': 'https://data.sec.gov/submissions/CIK0000320193.json'}, {'u': 'https://www.sec.gov/files/company_tickers_exchange.json'}]
try:
    req = urllib.request.Request(SITE + '/?vlst_want=' + tok, headers={'User-Agent': 'Mozilla/5.0 (compatible; VaultLabMirror/1.0; +https://vaultlab.kr)', 'Accept': 'application/json'})
    raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    want = json.loads(raw)
    print('볼트랩 목록:', len(want), '개')
except urllib.error.HTTPError as e:
    print('볼트랩 사이트 응답', e.code, '·', e.read()[:200].decode('utf-8', 'replace').replace('\n', ' '))
    print('→ 일단 기본 주소만으로 SEC 시험을 해요')
    want = SEED
except Exception as e:
    print('볼트랩 목록을 못 읽었어요:', str(e)[:200]); want = SEED
now = time.time()
todo = []
for w in want:
    u = w.get('u', '')
    if not re.match(r'^https://(www\.|data\.|efts\.)?sec\.gov/', u): continue
    h = hashlib.md5(u.encode('utf-8')).hexdigest()
    got = state.get(h, {}).get('at', 0)
    if now - got >= ttl(u): todo.append((0 if not got else 1, got, u, h))
todo.sort()
ok = bad = 0
for _, _, u, h in todo[:MAX]:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate'}), timeout=40)
        body = r.read()
        if r.headers.get('Content-Encoding') == 'gzip': body = gzip.decompress(body)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code; body = ('SECERR %d ' % e.code).encode() + e.read()[:300]
    except Exception as e:
        code = 0; body = ('SECERR 000 ' + str(e)).encode()
    if code == 200 or code == 404 or not os.path.exists(os.path.join(OUT, 'm', h + '.gz')):
        with gzip.open(os.path.join(OUT, 'm', h + '.gz'), 'wb') as f: f.write(body)
    state[h] = {'u': u, 'at': now if code in (200, 404) else state.get(h, {}).get('at', 0), 'c': code}
    ok += code == 200; bad += code != 200
    if code == 403 and bad >= 5 and ok == 0: print('SEC가 GitHub도 막았어요 (403)'); break
    time.sleep(GAP)
# 3일 넘게 아무도 안 찾은 자료는 정리
keep = {hashlib.md5(w['u'].encode('utf-8')).hexdigest() for w in want}
for h in list(state):
    if h not in keep and now - state[h].get('at', 0) > 3 * 86400:
        state.pop(h, None)
        try: os.remove(os.path.join(OUT, 'm', h + '.gz'))
        except OSError: pass
json.dump(state, open(state_p, 'w'))
print('받음 %d · 실패 %d · 대기 %d' % (ok, bad, max(0, len(todo) - MAX)))
print('SEC 결과:', ', '.join(sorted({str(v.get('c')) for v in state.values()})))
