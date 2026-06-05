#!/usr/bin/env python3
"""确定性合成「80 债依赖分析与安全批次计划」真相源 registry。
只读既有 JSON,从不读任何计划草稿(防自污染)。Phase4 子 agent 以本产物为分派根基,
但每个 agent 仍须在当前代码上独立 grep 回盘真实 file:line —— registry 的行号一律视为「待复核」。
"""
import json
import os

BASE = '/Users/lurenxing/Documents/GitHub/----'
FP   = BASE + '/.codestable/audits/2026-06-02-underwater-debt-census/fix-plan'
PD   = BASE + '/docs/_panorama_data'
OUT  = PD + '/phase4_dep_safety'

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

status = {d['id']: d for d in load(PD + '/debt_status_2026-06-05.json')['debts']}
index  = {d['id']: d for d in load(PD + '/debt_index_2026-06-05.json')['debts']}
intf   = load(PD + '/debt_interference.json')
truth  = load(FP + '/phase0/_truth.json')
p2     = load(FP + '/phase2/_phase2_index.json')
p1     = load(FP + '/phase1/_phase1_blast.json')

edges     = intf['edges']
pf        = intf['deb_primary_file']
deb_files = intf.get('deb_files', {})
clusters  = intf['clusters']
samefile  = truth['samefile_groups']
home      = truth['home']
verdict   = truth['verdict_map']
advprec   = {k: v.get('adv_precondition') for k, v in truth['debts'].items()}

def cluster_of(did):
    for c in clusters:
        if did in c.get('members', []):
            return c.get('cid', 'C?')
    return 'ISOLATED'

def edges_of(did):
    out = []
    for e in edges:
        a, b = e.get('a'), e.get('b')
        if did in (a, b):
            why = e.get('why', [])
            out.append({
                'other': b if a == did else a,
                'why': why,
                'same_file':  any(w.startswith('file:') for w in why),
                'same_symbol': any(w.startswith('sym:') for w in why),
            })
    return out

def siblings(did):
    sib = set()
    for mem in samefile.values():
        if did in mem:
            sib.update(m for m in mem if m != did)
    return sorted(sib)

# owner 须裁断的超集(来自 MASTER-PLAN §6 19 条 + 附录 C + 提示词 §六);宁可多标,agent 再复核
OWNER_PENDING = {
    'R09','R22','LB07','R71','R26','R11','R29','R52','R14','R43','LB08','R55',
    'R03','R19','R72','R44','R41','R40','R32','R34','R08','R15','R54','LB03','R24','R05','R67',
}

# 承重不可碰锚点(来自 §90 / PHASE0 §5 / PHASE1 §1);agent 落地前仍须按符号回盘确认禁区行
LB_NO_TOUCH = {
    'LB01': '禁区 operation_execution_feedback_service.py 硬拒分支(requested/effective_plan_role!=ROLE_ADOPTED|source_table!=SOURCE_SCHEDULE|scenario_id is not None→raise)+ _build_event_payload 写死 SOURCE_SCHEDULE/ROLE_ADOPTED/None 消毒层;只补注释,禁透传 context;最危险边↔R17 同 _build_event_payload 函数',
    'LB02': '禁区 execution_review.py 签名故意不收 plan_role/scenario_id + 恒 ROLE_ADOPTED 的 _resolve_plan/标签;只补注释,禁加形参统一四报表签名;LB02≡LB05 同点两 finding',
    'LB05': '同 LB02(execution_review.py 同一不对称的第二 finding,core-svc-domain 分区)',
    'LB06': '禁区 reports_page_support.py page_plan_resolution/page_date_range 写死 adopted,None + navigation_context.py is_execution_review 强制 adopted/清 scenario;只补注释;真实行号 off-by-one(报告:366/368→盘上:367/369)',
    'LB03': '已超前治理为 fail-closed(_parsed_summary_flag_is_true fail_closed=True)+ 可观测字段;禁按旧报告改 loud raise(latest_executable_official_version 全量扫历史=可用性放大事故);仅认账注释 + git add 守卫测试',
    'LB04': 'boolean_normalize.py 双实现是分层承重(下层 core.shared 供 core.models/algorithms);禁删 shared 改指 services(造 core.models→core.services 越层+导入环);唯一合法消重=上层 matrix 反向 delegate 到下层',
    'LB07': 'schedule_config_runtime_* 双栈 ScheduleConfigSnapshot 27 字段锁步;禁单边加字段;收敛前先补 parity;禁碰 coercion:470 graph_downstream_weight 置零 / :152-153 strict loud raise / :73-80 MISSING_POLICY_ERROR raise',
    'LB08': 'scheduler_public_errors.py LEGACY 正则桥(把中文串反解回 code,与 make_public_error 并存);禁删正则桥、禁改被 auto_assign_resource_errors 发出的文案而不同步正则;注释钉「文案与正则同生共死」',
    'R56': 'navigation_context.py 靠 endpoint/path 字面量匹配钉 execution_review→强制 adopted,零注释最脆弱;真正 rename 守卫=regression_plan_vs_actual_review:350-359 必须绑牢',
    'R58': 'scheduler_navigation_publish.py context.update 把 builder 已 gate 的 can_write_feedback 覆盖回未门控值;默认只补注释,剔除 update 须先验 builder-gated≡raw 且 keep_plan_guard_fields 契约绿',
    'R54': 'N1=high+load_bearing:plan-guard 字段投影散成 4 套手维列表(盘上已恶化,本轮新增 2 份);唯一合法修法=收口进 build_workbench_plan_context 全 4 套 delegate;漏拷 is_comparison/is_superseded_by_newer_version 任一=fail-OPEN 旧正式冒充现行',
    'R05': 'verdict=load_bearing:schedule_plan_query_repo team 双 join + 空 id 全量是 column_name 单列表达不了的承重第三轴;塌缩=班组静默失效/整页 500;必须先扩收口点再谈收敛',
    'R03': 'verdict-confirmed 承重:runner.py narrow-except CandidateTrialFailure 防 b81f8b3f 删掉的静默吞错复活;只补注释,禁改回 except Exception',
}

reg = {}
for did in index:
    s  = status.get(did, {})
    ix = index[did]
    reg[did] = {
        'id': did,
        'bucket': ix.get('bucket'),
        'home': home.get(did),
        'status_2026_06_05': s.get('status'),
        'severity': ix.get('severity'),
        'pathology': ix.get('pathology'),
        'partition': ix.get('partition'),
        'kind': ix.get('kind'),
        'load_bearing': ix.get('load_bearing'),
        'needs_adversarial': ix.get('needs_adversarial'),
        'adv_refuted': ix.get('adv_refuted'),
        'title': ix.get('title'),
        'old_location_DONT_TRUST': ix.get('location'),
        'primary_file': pf.get(did),
        'all_files': deb_files.get(did, []),
        'current_evidence_2026_06_05': s.get('evidence'),
        'cluster': cluster_of(did),
        'same_file_siblings': siblings(did),
        'interference_edges': edges_of(did),
        'verdict': verdict.get(did),
        'adv_precondition': advprec.get(did),
        'planned_batch_hint': p2.get(did, {}).get('batch'),
        'planned_deps_hint': p2.get(did, {}).get('deps'),
        'planned_fix_hint': p2.get(did, {}).get('fix'),
        'phase1_blast': p1.get(did),
        'owner_pending': did in OWNER_PENDING,
        'lb_no_touch': LB_NO_TOUCH.get(did),
    }

# 精简索引(主循环导航用,小)
idx = {}
for did, r in reg.items():
    idx[did] = {
        'id': did, 'bucket': r['bucket'], 'status': r['status_2026_06_05'],
        'sev': r['severity'], 'path': r['pathology'], 'lb': r['load_bearing'],
        'file': r['primary_file'], 'cluster': r['cluster'],
        'siblings': r['same_file_siblings'],
        'batch': r['planned_batch_hint'][:18] if r['planned_batch_hint'] else None,
        'owner_pending': r['owner_pending'],
        'needs_adv': r['needs_adversarial'], 'adv_refuted': r['adv_refuted'],
        'title': r['title'],
    }

# 簇拆分:C01 按 primary_file 分子簇 + 其余簇 + 孤点
from collections import defaultdict

clus_out = {}
for c in clusters:
    cid = c.get('cid', 'C?')
    mem = c.get('members', [])
    byfile = defaultdict(list)
    for m in mem:
        byfile[pf.get(m, '??')].append(m)
    clus_out[cid] = {
        'size': len(mem), 'members': mem,
        'files': c.get('files', []),
        'subclusters_by_primary_file': {k: v for k, v in sorted(byfile.items())},
    }
isolated = [d for d in index if cluster_of(d) == 'ISOLATED']
clus_out['ISOLATED'] = {'size': len(isolated), 'members': isolated}

os.makedirs(OUT + '/dossiers', exist_ok=True)
json.dump(reg, open(OUT + '/_registry.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(idx, open(OUT + '/_registry_index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(clus_out, open(OUT + '/_clusters.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 摘要
print('registry 条目数:', len(reg))
from collections import Counter

print('status 分布:', dict(Counter(r['status_2026_06_05'] for r in reg.values())))
print('cluster 分布:', dict(Counter(r['cluster'] for r in reg.values())))
print('owner_pending:', sorted(d for d in reg if reg[d]['owner_pending']))
print('load_bearing:', sorted(d for d in reg if reg[d]['load_bearing']))
print('needs_adversarial:', sorted(d for d in reg if reg[d]['needs_adversarial']))
print('孤点债:', isolated)
print('C01 子簇(按主文件,仅列 ≥2 债的):')
for cid, c in clus_out.items():
    if cid == 'ISOLATED':
        continue
    for f, mm in c.get('subclusters_by_primary_file', {}).items():
        if len(mm) >= 2:
            print(f'  [{cid}] {f}: {mm}')
print('待修+在途(需 dossier):', sorted(d for d in reg if reg[d]['status_2026_06_05'] in ('planned','in_progress')))
print('已修(作前置):', sorted(d for d in reg if reg[d]['status_2026_06_05']=='fixed'))
print('误标:', sorted(d for d in reg if reg[d]['status_2026_06_05']=='not_applicable'))
