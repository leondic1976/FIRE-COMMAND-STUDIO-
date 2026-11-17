import {useState} from 'react';
import {Clock3,Play,SkipForward} from 'lucide-react';
import {EventDefinition,SessionState,clock} from '../../../packages/domain-schemas';
import {Badge,Field} from './components';
import type {Run} from './App';
import './candidate-controls.css';

export function CandidateControls({session,elapsed,busy,control,run}:{session:SessionState;elapsed:number;busy:boolean;control:(op:string,extra?:Record<string,unknown>)=>Promise<void>;run:Run}){
 return <div className="candidate-list">{session.candidates?.map(event=><Candidate key={session.id+event.id} event={event} elapsed={elapsed} status={session.status} busy={busy} control={control} run={run}/>)}</div>;
}

function Candidate({event,elapsed,status,busy,control,run}:{event:EventDefinition;elapsed:number;status:string;busy:boolean;control:(op:string,extra?:Record<string,unknown>)=>Promise<void>;run:Run}){
 const [operation,setOperation]=useState<'defer'|'skip'|''>(''),[reason,setReason]=useState(''),[delay,setDelay]=useState(60);
 const deferred=(event.deferred_until||0)>elapsed,canChange=['RUNNING','PAUSED'].includes(status);
 const submit=()=>void run(async()=>{await control(operation,{event_id:event.id,reason,delay_seconds:delay});setOperation('');setReason('');},operation==='defer'?'연기 사유와 훈련시각을 기록했습니다.':'건너뛰기 사유를 기록했습니다. 메시지·장면 패치는 공개하지 않았습니다.');
 return <div className="candidate-card" data-candidate-id={event.id}><div className="candidate-heading"><Badge>{event.id}</Badge><strong>{event.title}</strong><small>{event.visibility==='PRIVATE'?'지정 역할 비공개':'공동화면 공개'} · {event.condition_met?'발생 조건 충족':'조건 대기'}{deferred&&` · ${clock(event.deferred_until||0)}까지 연기`}</small></div>
  <span className="candidate-patch">{event.patches.length}개 장면 변경</span><div className="candidate-actions"><button className="button primary" disabled={busy||status!=='RUNNING'||!event.condition_met||deferred} onClick={()=>void run(()=>control('release',{event_id:event.id}),'메시지와 장면 상태를 함께 반영했습니다.')}><Play size={14}/>승인·공개</button><button className="button" disabled={busy||!canChange} onClick={()=>{setOperation('defer');setReason('');}}><Clock3 size={14}/>연기</button><button className="button" disabled={busy||!canChange} onClick={()=>{setOperation('skip');setReason('');}}><SkipForward size={14}/>건너뛰기</button></div>
  <details className="candidate-preview"><summary>공개 전 메시지·상태 변경 확인 · {event.id}</summary><p><strong>{event.sender}</strong> · {event.channel}</p><p className="candidate-message">{event.text}</p><p className="small muted">아래는 훈련 제작자가 지정한 연출 변경입니다. 공학적 예측이나 현재 공용화면 상태가 아닙니다.</p>{event.patches.length?<div className="table-scroll"><table><thead><tr><th>객체/필드</th><th>변경 전</th><th>변경 후</th></tr></thead><tbody>{event.patches.map((patch,i)=><tr key={i}><td>{patch.feature_id} / {patch.field}</td><td>{JSON.stringify(patch.before)}</td><td>{JSON.stringify(patch.after)}</td></tr>)}</tbody></table></div>:<p className="small muted">장면 변경 없음 · 메시지만 공개합니다.</p>}</details>
  {operation&&<div className="candidate-reason" role="group" aria-label={`${event.id} ${operation==='defer'?'연기':'건너뛰기'} 기록`}><Field label={operation==='defer'?'연기 사유':'건너뛰기 사유'}><input value={reason} maxLength={2000} onChange={e=>setReason(e.target.value)}/></Field>{operation==='defer'?<Field label="훈련시계 기준 연기 시간 (초)"><input type="number" min={1} max={3600} step={1} value={delay} onChange={e=>setDelay(Number(e.target.value))}/></Field>:<p className="small warning">현재 후보를 건너뛰고 후속 후보로 이동합니다. 이 사건의 메시지·장면 변경은 적용하지 않으며 사유는 비공개 이력에 남습니다.</p>}<div className="button-row"><button className="button primary" disabled={busy||!canChange||!reason.trim()||(operation==='defer'&&(!Number.isInteger(delay)||delay<1||delay>3600))} onClick={submit}>사유 기록 후 {operation==='defer'?'연기':'건너뛰기'}</button><button className="button" onClick={()=>setOperation('')}>취소</button></div></div>}
 </div>;
}
