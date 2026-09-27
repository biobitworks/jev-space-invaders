#!/usr/bin/env python3
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
MAN=ROOT/'evidence/sponsor_source/SPONSOR_SOURCE_DATASET.json'
CACHE=ROOT/'artifacts/private/sponsor_source_freeze/2026-09-27'

def hp(prefix,*parts):
    payload=prefix.encode()+b'\0'+b'\0'.join(p if isinstance(p,bytes) else str(p).encode() for p in parts)
    return hashlib.sha256(payload).digest()
def merkle(nodes):
    nodes=list(nodes)
    if not nodes:return hashlib.sha256(b'FMO_EMPTY_V1').digest()
    while len(nodes)>1:
        if len(nodes)%2:nodes.append(nodes[-1])
        nodes=[hp('FMO_NODE_V1',nodes[i],nodes[i+1]) for i in range(0,len(nodes),2)]
    return nodes[0]

d=json.loads(MAN.read_text())
errors=[]; by_group={}
for rec in d['files']:
    p=CACHE/rec['path']
    if not p.exists(): errors.append('MISSING:'+rec['path']); continue
    b=p.read_bytes(); raw=hashlib.sha256(b).hexdigest()
    if len(b)!=rec['bytes']: errors.append('SIZE:'+rec['path'])
    if raw!=rec['sha256']: errors.append('SHA256:'+rec['path'])
    leaf=hp('FMO_LEAF_V1',rec['path'],len(b),raw).hex()
    if leaf!=rec['fmo_leaf']: errors.append('LEAF:'+rec['path'])
    by_group.setdefault(rec['path'].split('/',1)[0],[]).append((rec['path'],bytes.fromhex(leaf)))
commits=[]
for g in sorted(by_group):
    vals=[v for _,v in sorted(by_group[g])]
    gr=merkle(vals).hex()
    if gr!=d['fmo']['groups'][g]['merkle_root']: errors.append('GROUP:'+g)
    gc=hp('FMO_GROUP_V1',g,gr).hex()
    if gc!=d['fmo']['groups'][g]['group_commitment']: errors.append('GROUP_COMMIT:'+g)
    commits.append(bytes.fromhex(gc))
root=merkle(commits).hex()
if root!=d['fmo']['root']: errors.append('ROOT')
print('SPONSOR_SOURCE_VERIFY='+('PASS' if not errors else 'FAIL'))
print('SPONSOR_FMO_ROOT='+root)
print('LEAF_COUNT='+str(sum(len(v) for v in by_group.values())))
if errors:
    print('\n'.join(errors)); sys.exit(2)
