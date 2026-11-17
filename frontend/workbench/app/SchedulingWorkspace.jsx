import React from './shared/runtime/react.js';
import A from './RunJobAPI.js';
import U from './RunJobControls.jsx';
import RunHistoryAPI from './RunHistoryAPI.js';
import RunCandidateWorkspace from './RunCandidateWorkspace.jsx';
import RunAdoptionAction from './RunAdoptionAction.jsx';
import DecisionHistoryAPI from './DecisionHistoryAPI.js';
import PreflightWorkspace from './PreflightWorkspace.jsx';
import RunJobPanel from './RunJobPanel.jsx';
import APSPlanNavigation from './PlanNavigation.js';
import WorkbenchNavigation from './WorkbenchNavigation.js';
import RunHistoryWorkspace from './RunHistoryWorkspace.jsx';
import PlanWorkspace from './PlanWorkspace.jsx';
import { ref48 } from './shared/contract/kit.js';
import { WorkbenchError } from './WorkbenchReferences.jsx';

// 「排产记录」总是回到记录列表专题：列表条件取返回链上最近的排产记录页（含本页），去掉快照钉。
function runHistoryDestination(context) {
  const found = WorkbenchNavigation.origin(context, value => value.source === 'run_history');
  return { view: 'analysis', context: { source: 'run_history', history_topic: 'run_catalog',
    history_query: RunHistoryAPI.returnContext(RunHistoryAPI.scope(found ? found.history_query : undefined)) } };
}
// 试调的返回信封 back 是打开试调的页面及其当前状态，由调用方给出。
function trialAction(onNavigate, { planRef, candidateRef, scope, query, disabled, taskOrigin, back, label = '试调' }) {
  const display = { query };
  if (scope.range_start && scope.range_end) { display.range_start = scope.range_start; display.range_end = scope.range_end; }
  if (scope.batch_ref) display.batch_refs = [scope.batch_ref];
  return <U.Button icon="square-pen" disabled={disabled} onClick={() => onNavigate('trial', {
    base: candidateRef ? { candidate_ref: candidateRef } : { plan_ref: planRef }, scope: display,
    ...(taskOrigin ? { task_origin: taskOrigin } : {}), return_to: back,
  })}>{label}</U.Button>;
}
function ReadRun({ runRef, onNavigate, initialContext, runHistoryReturn }) {
  const validRef = ref48(runRef);
  const [record, setRecord] = React.useState(null), [error, setError] = React.useState(null);
  const [checking, setChecking] = React.useState(false), [verified, setVerified] = React.useState(false), [retryPaused, setRetryPaused] = React.useState(false);
  const [paused, setPaused] = React.useState(document.hidden), [revision, refresh] = React.useReducer(v => v + 1, 0);
  React.useEffect(() => {
    if (!validRef) return undefined;
    setRetryPaused(false);
    let disposed = false, timer, controller, querying = false, done = false, attempt = 0, unsettledSince = null;
    function schedule() { if (!disposed && !done && !document.hidden) timer = setTimeout(read, A.pollDelay(attempt++)); }
    // Same rule as the candidate panel: 60 seconds of failed reads stop the automatic query; the refresh button restarts it.
    function unresolved(started) {
      if (unsettledSince === null) unsettledSince = started;
      if (Date.now() - unsettledSince >= 60000) { done = true; setRetryPaused(true); }
    }
    async function read() {
      if (disposed || querying || document.hidden || done) return;
      querying = true; const localController = new AbortController(); controller = localController; setChecking(true); setVerified(false); const started = Date.now();
      try {
        const value = await A.get(runRef, localController.signal);
        if (disposed || localController.signal.aborted) return;
        if (!value.recovery_required) attempt = 0;
        setRecord(value); setVerified(true); setError(null); unsettledSince = null; done = A.terminal(value);
      } catch (problem) {
        // 只读查询：错误对象原样交给显示层（后端或传输层的中文说明），不套用命令“结果未知”的说法。
        if (!disposed && !localController.signal.aborted) { setError(problem); setVerified(false); unresolved(started); }
      } finally {
        if (controller === localController) {
          querying = false;
          if (!disposed) {
            setChecking(false);
            if (!localController.signal.aborted) schedule();
            else if (!document.hidden && !done) read();
          }
        }
      }
    }
    function visibility() {
      setPaused(document.hidden); clearTimeout(timer);
      if (document.hidden) { if (controller) controller.abort(); }
      else { attempt = 0; if (!querying) read(); }
    }
    document.addEventListener('visibilitychange', visibility); visibility();
    return () => { disposed = true; clearTimeout(timer); if (controller) controller.abort(); document.removeEventListener('visibilitychange', visibility); };
  }, [runRef, revision]);
  const historyReturn = <HistoryReturn context={initialContext} onNavigate={onNavigate} />;
  const newRun = <U.Button icon="plus" onClick={() => onNavigate('run', {})}>新排产</U.Button>;
  const navigation = <Navigation>{historyReturn}<U.Button icon="history" onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>排产记录</U.Button>{newRun}</Navigation>;
  if (record && verified && record.result_persisted && record.candidates.length > 0) return <RunCandidateWorkspace view="analysis"
    initialContext={{ ...initialContext, run_ref: runRef }} onNavigate={onNavigate} runHistoryReturn={runHistoryReturn} navigation={<Navigation>{historyReturn}{newRun}</Navigation>} headerTitle="本次排产结果" runStatus={record.state} runTiming={record}
    renderAdoption={(candidateRef, metadata) => <RunAdoptionAction candidateRef={candidateRef} {...metadata} onNavigate={onNavigate} />}
    renderTrial={value => trialAction(onNavigate, value)} />;
  return <section className="plana run-job-panel rj-status-workspace" aria-label="本次排产">
    {!validRef ? <><div className="rj-heading rj-business-heading"><h2>本次排产</h2>{navigation}</div><p role="alert">这条排产记录已失效，请点「排产记录」重新选择。</p></> : <>
      <U.Record run={record} paused={paused} checking={checking} verified={verified} retryPaused={retryPaused} retryHint="请点「刷新本次排产」再次核对。" onNavigate={onNavigate} navigation={navigation}
        actions={<U.Button icon="refresh-cw" aria-label="刷新本次排产" busy={checking} onClick={refresh} />} />
      <WorkbenchError error={error} />
    </>}
  </section>;
}
function Navigation({ children }) {
  return <div className="scheduling-navigation">{children}</div>;
}
function HistoryReturn({ context, onNavigate }) {
  const found = DecisionHistoryAPI.historyOrigin(context);
  return found ? <U.Button icon="chevron-left" onClick={() => onNavigate('analysis', found)}>返回历史走势</U.Button> : null;
}
function RunWorkspace({ variant, onNavigate, initialContext }) {
  const runHistoryReturn = runHistoryDestination(initialContext);
  const history = <><HistoryReturn context={initialContext} onNavigate={onNavigate} /><U.Button icon="history" onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>排产记录</U.Button></>;
  return variant === 'candidate' ? <ReadRun key={initialContext.run_ref} runRef={initialContext.run_ref} initialContext={initialContext} onNavigate={onNavigate} runHistoryReturn={runHistoryReturn} /> :
    <PreflightWorkspace initialContext={initialContext} onNavigate={onNavigate} actions={history}
      renderRunPanel={(data, continuation) => <RunJobPanel preflight={data} onNavigate={onNavigate} onRecheck={continuation.onRecheck} preflightOwner={continuation.confirmationOwner} />} />;
}
// variant 是导航准入按受控声明选出的状态变体：candidate 候选与方案对比，history 排产记录，plan 正式计划。
function PlanCenterWorkspace({ view, variant, onNavigate, initialContext }) {
  const context = initialContext, candidate = variant === 'candidate', history = variant === 'history';
  let formal = null, formalError = null;
  if (variant === 'plan') { try { formal = APSPlanNavigation.accept(context); } catch (error) { formalError = error; } }
  const runHistoryReturn = runHistoryDestination(context);
  function renderTrial(value) { return trialAction(onNavigate, value); }
  const navigation = <Navigation>
    {formal && formal.return_to && <U.Button icon="chevron-left" onClick={() => onNavigate(formal.return_to.view, formal.return_to.context)}>返回</U.Button>}
    {!history && <HistoryReturn context={context} onNavigate={onNavigate} />}
    <U.Button icon="files" aria-pressed={!candidate && !history} onClick={() => onNavigate(view, {})}>计划版本</U.Button>
    {!candidate && <U.Button icon="history" aria-pressed={history} onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>排产记录</U.Button>}
  </Navigation>;
  return candidate ? <RunCandidateWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate} runHistoryReturn={runHistoryReturn} navigation={navigation}
    renderAdoption={(candidateRef, metadata) => <RunAdoptionAction candidateRef={candidateRef} {...metadata} onNavigate={onNavigate} />} renderTrial={renderTrial} /> : history ?
    <RunHistoryWorkspace initialContext={context.history_query} pageContext={context} onNavigate={onNavigate} navigation={navigation} /> :
    formalError ? <section className="plana plan-workspace">{navigation}<WorkbenchError error={formalError} fallback="打开计划的定位信息无效，请从来源页面重新打开。" /></section> :
    <PlanWorkspace view={view} initialContext={formal} onNavigate={onNavigate} renderTrial={renderTrial} navigation={navigation} />;
}
export { PlanCenterWorkspace, RunWorkspace };
export default PlanCenterWorkspace;
