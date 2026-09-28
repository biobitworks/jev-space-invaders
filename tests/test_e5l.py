import json
from src.liquid_client import LiquidOllamaDecider,ACTION_SCHEMA
from experiments.e5l_episodes import ARMS,_ctx
def state():
    return {"encoding":"perception_v1","coords":"","step":0,"score":0.0,"lives":3,"previous_action":"NOOP",
            "ship":{"x":80,"x_min":77,"x_max":83,"dx":None},"bombs":[],"own_shots":[],"unknown_shots":[],
            "aliens":{"present":True,"count_est":10,"rows":2,"x_min":20,"x_max":140,"y_min":40,"y_max":90,"column_centres_x":[40]},
            "shields":[]}
def test_liquid_schema_and_request_no_decision_leak():
    d=LiquidOllamaDecider()
    body=json.loads(d.request_body({"state":state()}))
    assert body["format"]==ACTION_SCHEMA
    text=json.dumps(body)
    for bad in ("recommended_action","recommended_move","golden_action","best_action"): assert bad not in text
def test_e5l_context_contracts():
    s=state()
    raw=_ctx("LQ_RAW",s,[])
    full=_ctx("LV_VITA01",s,[])
    assert raw=={"state":s}
    assert full["state"]==s and "history" in full and "anticube" in full and "path_distribution" in full
    assert ARMS=={"LQ_RAW":"A0_RAW","LV_VITA01":"A5_VITA01_FULL"}

