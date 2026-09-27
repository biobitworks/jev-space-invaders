#!/usr/bin/env python3
import pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
patterns=[
 ('OPENAI_STYLE_KEY',re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b')),
 ('AWS_ACCESS_KEY',re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
 ('BEARER_TOKEN',re.compile(r'Bearer\s+[A-Za-z0-9._~-]{20,}',re.I)),
 ('PRIVATE_KEY',re.compile(r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY')),
]
secret_vars={'TYPESAFE_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','MITOSIS_API_KEY','TENKI_API_KEY','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN'}
hits=[]
for fn in files:
    p=ROOT/fn
    if not p.is_file(): continue
    try: s=p.read_text(errors='ignore')
    except Exception: continue
    for name,pat in patterns:
        if pat.search(s): hits.append((fn,name))
    for line in s.splitlines():
        if '=' not in line or line.lstrip().startswith('#'): continue
        k,v=line.split('=',1); k=k.strip(); v=v.strip().strip('"\'')
        if k in secret_vars and v and not (v.startswith('${') or v.startswith('<') or v.lower() in {'changeme','example','placeholder'}):
            hits.append((fn,'NONEMPTY_SECRET_ASSIGNMENT:'+k))
print('SECRET_SCAN='+('PASS' if not hits else 'FAIL'))
print('SCANNED_FILES='+str(len(files)))
if hits:
    for x in hits: print('HIT='+repr(x))
    sys.exit(2)
