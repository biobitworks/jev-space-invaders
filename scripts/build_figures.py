#!/usr/bin/env python3
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

R=Path(__file__).resolve().parents[1]
F=R/"publication/figures"
F.mkdir(parents=True,exist_ok=True)
D=json.loads((R/"publication/data/plot_data.json").read_text())

def save(fig,name,sources,claims):
    fig.tight_layout()
    fig.savefig(F/(name+".pdf"),bbox_inches="tight")
    fig.savefig(F/(name+".png"),dpi=180,bbox_inches="tight")
    plt.close(fig)
    meta={"figure":name,"source_refs":sources,"claim_refs":claims}
    (F/(name+".json")).write_text(json.dumps(meta,indent=2)+"\n")

def flow(name,labels,title,sources,claims):
    fig,ax=plt.subplots(figsize=(10,2.6))
    ax.axis("off")
    xs=[.07+i*(.86/(len(labels)-1)) for i in range(len(labels))]
    for i,(x,l) in enumerate(zip(xs,labels)):
        ax.add_patch(FancyBboxPatch((x-.055,.38),.11,.24,boxstyle="round,pad=0.015",fill=False))
        ax.text(x,.50,l,ha="center",va="center",fontsize=9)
        if i<len(labels)-1:
            ax.annotate("",xy=(xs[i+1]-.06,.50),xytext=(x+.06,.50),arrowprops=dict(arrowstyle="->"))
    ax.set_title(title)
    save(fig,name,sources,claims)

flow("F1_architecture",
     ["Evidence","Vithia-S0","VitaState","ContextPacket","S1","Decision","Observation","Successor"],
     "0-Vita-1 evidence/context/decision loop",
     ["vita01/VITA01_TERMINOLOGY_V2.json","vita01/S01_PROTOCOL_SPEC_DRAFT.md"],
     ["ARCH::S0_ROLE"])

flow("F2_custody",
     ["Source FCO","Context FCO","Typed FCG","Breakpoint root","MMR append","Verified successor"],
     "Identity, relationships, and append-only custody",
     ["docs/BREAKPOINT_PROTOCOL.md","governance/MMR_LEDGER.json"],
     ["GOV::MMR24"])

fig,ax=plt.subplots(figsize=(9,3))
labs=["E0\nIdentity","E1\nRule sets","E2\nHistory","E3\nUncertainty","E4A\nFrozen world"]
ax.plot(range(5),[1]*5,marker="o")
for i,l in enumerate(labs):
    ax.text(i,1.04,l,ha="center",va="bottom")
ax.set_xlim(-.3,4.3)
ax.set_ylim(.92,1.15)
ax.set_yticks([])
ax.set_xticks([])
ax.set_title("Progressive deterministic/contextual experiment ladder")
save(fig,"F3_experiment_ladder",["publication/data/experiment_summary.csv"],["LIMIT::E4A"])

fig,ax=plt.subplots(figsize=(7,4))
p=D["E1"]["h1d_fraction"]
lo,hi=D["E1"]["h1d_ci"]
th=D["E1"]["threshold"]
ax.bar(["H1d rank-1"],[p],yerr=[[p-lo],[hi-p]],capsize=6)
ax.axhline(th,linestyle="--",label="preregistered 0.90 threshold")
ax.set_ylim(0,1.02)
ax.set_ylabel("Fraction")
ax.legend()
ax.set_title("E1: H1d misses preregistered threshold")
save(fig,"F4_e1_outcomes",["publication/data/plot_data.json"],["E1_ECA::H1d","E1_ECA::H1e","E1_ECA::H1e_v2"])

fig,ax=plt.subplots(figsize=(7,4))
mean=D["E2"]["mean_accuracy_difference_correct_minus_shuffled"]
lo,hi=D["E2"]["bootstrap95_accuracy_difference"]
vals=[1.0,1.0-mean]
ax.bar(["Correct history","Shuffled history"],vals)
ax.set_ylim(0,1.05)
ax.set_ylabel("Accuracy")
ax.text(.5,.20,f"paired accuracy delta = {mean:.3f}\n95% bootstrap [{lo:.3f}, {hi:.3f}]",ha="center")
ax.set_title("E2: current evidence with different history changes context")
save(fig,"F5_e2_history",
     ["publication/data/plot_data.json","data/s01/S01_LIFE_CONTEXT_RESULTS_V1/history_controls.jsonl"],
     ["E2_LIFE::H2d"])

fig,ax=plt.subplots(figsize=(7,4))
m1=1.9227
m0=1.7175
delta=D["E3"]["H3b"]["mean_paired_gain_difference"]
lo,hi=D["E3"]["H3b"]["bootstrap95_mean_difference"]
ax.bar(["Max-EIG question","Random question"],[m1,m0])
ax.set_ylabel("Mean realized information gain (bits)")
ax.text(.5,min(m0,m1)*.45,f"paired delta = {delta:.3f} bits\n95% bootstrap [{lo:.3f}, {hi:.3f}]",ha="center")
ax.set_title("E3: information-directed questions outperform random")
save(fig,"F6_e3_information_gain",
     ["publication/data/plot_data.json","data/s01/S01_MINESWEEPER_RESULTS_V1/rows.jsonl"],
     ["E3_MINESWEEPER::H3b","E3_MINESWEEPER::H3c"])

flow("F7_e4a_pipeline",
     ["RGB frames","Perception","Frozen snapshot","VitaState","ContextPacket","System-1\nNOT TESTED"],
     "E4A frozen preprocessing boundary",
     ["governance/breakpoints/0020-e4a-prereg.json"],
     ["LIMIT::E4A"])

led=json.loads((R/"governance/MMR_LEDGER.json").read_text())["entries"]
fig,ax=plt.subplots(figsize=(10,3.2))
seq=[e["seq"]+1 for e in led]
ax.scatter(seq,[1]*len(seq),s=18)
for e,x in zip(led,seq):
    if e["bp_id"] in ["UFA-JEV-BP-0011","UFA-JEV-BP-0013","UFA-JEV-BP-0015","UFA-JEV-BP-0017",
                      "UFA-JEV-BP-0019","UFA-JEV-BP-0020","UFA-JEV-BP-0022","UFA-JEV-BP-0024"]:
        ax.text(x,1.02,e["bp_id"].replace("UFA-JEV-",""),rotation=60,ha="left",fontsize=7)
ax.set_ylim(.95,1.16)
ax.set_yticks([])
ax.set_xlabel("Ordered scientific MMR leaf / breakpoint sequence")
ax.set_title("Scientific breakpoint lineage through the publication evidence-lock predecessor")
save(fig,"F8_breakpoint_timeline",["governance/MMR_LEDGER.json"],["GOV::MMR24"])
