import {useEffect,useRef,useState} from 'react';
import {Download,FileJson,Upload} from 'lucide-react';
import {api,download} from './api';
import './configuration-files.css';

type Preview={name:string;roles:number;persons:number;events:number;warnings:string[];issues:{gate:string;message:string;severity:string}[];sha256:string};

export function ConfigurationFiles({exerciseId,beforeExport,onImported}:{exerciseId:string;beforeExport:()=>Promise<unknown>;onImported:(id:string)=>Promise<void>}){
 const [file,setFile]=useState<File|null>(null),[preview,setPreview]=useState<Preview|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const active=useRef(true),importKey=useRef('');
 useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
 const run=async(task:()=>Promise<void>)=>{setError('');setBusy(true);try{await task();}catch(e){if(active.current)setError(e instanceof Error?e.message:'설정 파일을 확인해 주세요.');}finally{if(active.current)setBusy(false);}};
 const choose=(chosen:File)=>void run(async()=>{
  setFile(null);setPreview(null);
  if(chosen.size>2*1024*1024)throw Error('훈련 설정 JSON은 2MB 이하여야 합니다.');
  const body=new FormData();body.set('file',chosen);
  const result=await api<Preview>('/configurations/preview',{method:'POST',body});
  if(!active.current)return;
  importKey.current=crypto.randomUUID();setFile(chosen);setPreview(result);
 });
 return <section className="panel configuration-files" aria-label="훈련 설정 JSON">
  <div className="configuration-heading"><div><strong><FileJson size={18}/> 훈련 설정 파일</strong><p>역할·배치·장면·사건 설정을 JSON으로 보관하고, 웹판과 로컬판에서 다시 불러옵니다.</p></div>
   <div className="button-row"><button className="button" disabled={busy} onClick={()=>void run(async()=>{await beforeExport();if(active.current)await download(`/exercises/${encodeURIComponent(exerciseId)}/configuration`,'training-configuration.json');})}><Download size={15}/> 설정 JSON 저장</button>
    <label className={`button ${busy?'disabled':''}`}><Upload size={15}/> 설정 JSON 불러오기<input type="file" accept=".json,application/json" aria-label="훈련 설정 JSON 파일" disabled={busy} onChange={e=>{const chosen=e.currentTarget.files?.[0];e.currentTarget.value='';if(chosen)choose(chosen);}}/></label></div>
  </div>
  {error&&<p className="alert error" role="alert">{error}</p>}
  {preview&&<div className="configuration-preview"><h3>설정 파일 미리보기 · {preview.name}</h3><p>역할 {preview.roles}개 · 참석자 {preview.persons}명 · 사건 {preview.events}개</p><ul>{preview.warnings.map(item=><li key={item}>{item}</li>)}</ul>
   {preview.issues.length>0&&<details><summary>다시 확인할 준비 항목 {preview.issues.length}개</summary><ul>{preview.issues.map((item,index)=><li key={index}>{item.gate} · {item.message}</li>)}</ul></details>}
   <button className="button primary" disabled={busy||!file} onClick={()=>void run(async()=>{if(!file)return;const body=new FormData();body.set('file',file);const result=await api<{id:string}>('/configurations/import',{method:'POST',body,headers:{'Idempotency-Key':importKey.current}});if(active.current)await onImported(result.id);})}>새 편집본으로 불러오기</button>
  </div>}
  <small className="muted">이 파일은 훈련 설정입니다. 실행 기록·평가·첨부자료를 포함하는 전체 백업은 별도로 보관하세요.</small>
 </section>;
}
