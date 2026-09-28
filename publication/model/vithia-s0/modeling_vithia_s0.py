"""Public Vithia-S0 / 0-Vita-1 reference packet builder.

This contains no learned weights and no private System-0 kernel.
It mirrors the public packet boundary used by the repository.
"""
from __future__ import annotations
import hashlib, json

FORBIDDEN_KEYS={"recommended_action","recommended_move","golden_action","best_action"}

def canonical_bytes(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def content_id(obj):
    return "sha256:"+hashlib.sha256(canonical_bytes(obj)).hexdigest()

def _keys(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj,list):
        for v in obj:
            yield from _keys(v)

def make_context_packet(domain,source_atoms,context,legal_actions,question,provider,
                        compile_ms=0.0,anticube=None,path_summary=None,private_commitment=None):
    packet={"schema":"S01_CONTEXT_PACKET_V1","domain":domain,"source_atoms":source_atoms,
            "context":context,"legal_actions":legal_actions,"question":question,
            "s0_provider":provider,"s0_compile_ms":round(float(compile_ms),4)}
    if anticube is not None: packet["anticube"]=anticube
    if path_summary is not None: packet["path_summary"]=path_summary
    if private_commitment is not None: packet["private_commitment"]=private_commitment
    bad=FORBIDDEN_KEYS & set(_keys(packet))
    if bad: raise ValueError("System 0 packet contains decision leakage: "+repr(sorted(bad)))
    packet["packet_id"]=content_id(packet)
    return packet
