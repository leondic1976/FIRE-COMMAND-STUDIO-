import {useEffect,useRef,useState} from 'react';
import {Database,Download,ShieldCheck} from 'lucide-react';
import {Exercise,ExternalFact,ExternalLayer,Source,Subject,formatKST} from '../../../packages/domain-schemas';
import {api,post} from './api';
import {Badge,Field} from './components';
import type {Run} from './App';
import './external-data.css';

type Provider='building_registry'|'weather'|'hydrant';
interface ProviderState {id:string;available:boolean;implemented?:boolean;reason:string;live_verified?:boolean}
interface Intake {id:string;exercise_id:string;request:{provider:Provider;query:Record<string,unknown>};batch:{provider:Provider;source:Source;retrieved_at:string;raw_sha256:string;records:ExternalFact[];total_count:number;warnings:string[]}}
const providerNames:Record<Provider,string>={building_registry:'건축물대장 표제부',weather:'기상청 초단기실황',hydrant:'소방용수시설 후보'};

function initialTime(){
 const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',hourCycle:'h23'}).formatToParts(new Date(Date.now()-3600000));
 const part=(name:string)=>parts.find(value=>value.type===name)?.value||'';
 return {date:`${part('year')}-${part('month')}-${part('day')}`,time:`${part('hour')}:00`};
}

export function describeExternalFact(provider:Provider,record:ExternalFact){
 const f=record.fields;
 if(provider==='building_registry')return `지상 ${f.floors_above??'미제공'}층 · 지하 ${f.floors_below??'미제공'}층 · ${f.use||'용도 미제공'} · ${f.road_address||f.address||'주소 미제공'} · 자료 기준 ${f.source_date||'미제공'}`;
 if(provider==='weather')return `${f.missing||f.value===null?'관측값 결측·미제공':`${f.value} ${f.unit||''}`} · 관측 ${f.observed_at?formatKST(String(f.observed_at)):'시각 미제공'}`;
 return `위치 ${f.latitude}, ${f.longitude} · ${f.address||'주소 미제공'} · 자료 기준 ${f.source_date||'미제공'} · 현재 사용 가능 여부 미확인`;
}

export function ReferenceFacts({subject}:{subject:Subject}){
 const layers=subject.external_layers||[];
 if(!layers.length)return null;
 return <details className="reference-facts"><summary><Database size={16}/>공공 기준자료 {layers.length}종 · 현장 실측·현재 사용 가능 보증 아님</summary>
  {layers.map(layer=><article key={layer.id}><h3>{providerNames[layer.provider]}</h3><p>{layer.source.provider} · 기준 {layer.source.as_of} · 수집 {formatKST(layer.retrieved_at)}</p>
   <ul>{layer.records.map(record=><li key={record.external_id}><strong>{record.name}</strong><span>{describeExternalFact(layer.provider,record)}</span></li>)}</ul>
   {layer.warnings.map(warning=><small key={warning}>{warning}</small>)}<a href={layer.source.url} target="_blank" rel="noreferrer">원천 자료 안내</a></article>)}
 </details>;
}

export function ExternalDataPanel({exercise,persist,refresh,refreshLists,run}:{exercise:Exercise;persist:()=>Promise<number>;refresh:()=>Promise<void>;refreshLists:()=>Promise<void>;run:Run}){
 const [providers,setProviders]=useState<ProviderState[]>([]),[provider,setProvider]=useState<Provider>('building_registry'),[statusError,setStatusError]=useState('');
 const [parcel,setParcel]=useState({sigunguCd:'',bjdongCd:'',bun:'',ji:'0000',platGbCd:'0'}),[weather,setWeather]=useState(()=>({...initialTime(),nx:'',ny:''}));
 const [page,setPage]=useState(1),[intake,setIntake]=useState<Intake|null>(null),[selected,setSelected]=useState<string[]>([]),[buildingId,setBuildingId]=useState('B01');
 const [fields,setFields]=useState<string[]>(['floors','use']),[ack,setAck]=useState(false),[note,setNote]=useState(''),[working,setWorking]=useState(false);
 const currentExercise=useRef(exercise.id);currentExercise.current=exercise.id;
 useEffect(()=>{setIntake(null);setSelected([]);setAck(false);setNote('');setBuildingId('B01');},[exercise.id]);
 useEffect(()=>{const controller=new AbortController();void api<ProviderState[]>('/providers',{signal:controller.signal}).then(setProviders).catch(error=>{if(!controller.signal.aborted)setStatusError(String(error));});return()=>controller.abort();},[]);
 const status=providers.find(value=>value.id===provider);
 const reset=()=>{setIntake(null);setSelected([]);setAck(false);};
 const queryValid=provider==='building_registry'?/^\d{5}$/.test(parcel.sigunguCd)&&/^\d{5}$/.test(parcel.bjdongCd)&&/^\d{4}$/.test(parcel.bun)&&/^\d{4}$/.test(parcel.ji):provider==='weather'?!!weather.date&&/^\d{2}:00$/.test(weather.time)&&Number(weather.nx)>=1&&Number(weather.nx)<=149&&Number(weather.ny)>=1&&Number(weather.ny)<=253:page>=1;
 const collect=()=>void run(async()=>{setWorking(true);const id=exercise.id;try{
   const version=await persist();
   const query=provider==='building_registry'?{...parcel,page,per_page:100}:provider==='weather'?{base_date:weather.date.replaceAll('-',''),base_time:weather.time.replace(':',''),nx:Number(weather.nx),ny:Number(weather.ny)}:{page,per_page:100};
   const result=await post<Intake>(`/exercises/${id}/external-data/preview`,{expected_state_version:version,request:{provider,query}});
   if(currentExercise.current!==id)return;
   setIntake(result);setSelected(provider==='building_registry'?result.batch.records.slice(0,1).map(value=>value.external_id):provider==='weather'?result.batch.records.map(value=>value.external_id):[]);setAck(false);
  }finally{setWorking(false);}},'수집 후보를 보존했습니다. 출처와 항목을 검토한 뒤 반영하세요.');
 const apply=()=>void run(async()=>{if(!intake)return;setWorking(true);try{
   const version=await persist();
   await post(`/exercises/${exercise.id}/external-data/${intake.id}/apply`,{expected_state_version:version,selected_ids:selected,building_id:buildingId,fields,approved_for_training:ack,note});
   await refresh();await refreshLists();reset();setNote('');
  }finally{setWorking(false);}},'검토한 기준자료를 초안에 반영했습니다. 리허설·발행은 다시 확인하세요.');
 return <section className="external-data-panel panel"><div className="panel-title"><div><Database size={18}/>공공 기준자료 수집·검토</div><Badge tone="orange">초안 반영 · 발행본 고정</Badge></div>
  <div className="padded"><p>수집만으로 건물·상황은 바뀌지 않습니다. 이용권·기준시각·좌표·항목을 확인하고 반영하세요. 외부 연결 장애가 나도 수동 제작과 로컬 훈련은 계속할 수 있습니다.</p>
   {statusError&&<p className="alert error">제공 상태 조회 실패: {statusError}</p>}
   <fieldset disabled={exercise.published||working} className="external-inputs"><Field label="공공 자료 종류"><select value={provider} onChange={e=>{setProvider(e.target.value as Provider);reset();}}>{Object.entries(providerNames).map(([id,name])=><option value={id} key={id}>{name}</option>)}</select></Field>
    <p className="external-status">{status?.available?'연결 설정 있음 · 실응답과 항목은 수집 후 검토':status?.reason||'제공 상태 확인 중'}</p>
    {!status?.available&&<p className="small muted">관리자가 기관 승인·제공처 연결을 설정해야 수집할 수 있습니다. 키는 이 화면에 입력하지 않습니다.</p>}
    {provider==='building_registry'&&<div className="form-grid">
     {(['sigunguCd','bjdongCd','bun','ji'] as const).map(key=><Field key={key} label={({sigunguCd:'시군구 코드 (5자리)',bjdongCd:'법정동 코드 (5자리)',bun:'본번 (4자리)',ji:'부번 (4자리)'})[key]}><input value={parcel[key]} inputMode="numeric" maxLength={key==='sigunguCd'||key==='bjdongCd'?5:4} onChange={e=>{setParcel(value=>({...value,[key]:e.target.value}));reset();}}/></Field>)}
     <Field label="대지 구분"><select value={parcel.platGbCd} onChange={e=>{setParcel(value=>({...value,platGbCd:e.target.value}));reset();}}><option value="0">대지</option><option value="1">산</option><option value="2">블록</option></select></Field>
    </div>}
    {provider==='weather'&&<div className="form-grid"><Field label="관측 기준일 (KST)"><input type="date" value={weather.date} onChange={e=>{setWeather(value=>({...value,date:e.target.value}));reset();}}/></Field><Field label="관측 기준시각 (KST 정시)"><input type="time" step={3600} value={weather.time} onChange={e=>{setWeather(value=>({...value,time:e.target.value}));reset();}}/></Field>{(['nx','ny'] as const).map(key=><Field key={key} label={`관측 격자 ${key.toUpperCase()}`}><input type="number" min={1} max={key==='nx'?149:253} value={weather[key]} onChange={e=>{setWeather(value=>({...value,[key]:e.target.value}));reset();}}/></Field>)}</div>}
    {provider!=='weather'&&<Field label="조회 페이지 (최대 100개 항목씩)"><input type="number" min={1} max={provider==='hydrant'?1000:100} value={page} onChange={e=>{setPage(Number(e.target.value));reset();}}/></Field>}
    <button className="button" disabled={!queryValid||!status?.available} onClick={collect}><Download size={15}/>수집·미리보기</button>
    {intake&&<div className="external-preview"><h3>수집 후보 {intake.batch.records.length}개 / 제공처 전체 {intake.batch.total_count}개</h3><p>수집 {formatKST(intake.batch.retrieved_at)} · 이용권 미확인 · 실측/현장 검증 전</p>
     {intake.batch.warnings.map(warning=><p className="alert info" key={warning}>{warning}</p>)}
     <div className="external-records">{intake.batch.records.map(record=><label className="external-record" key={record.external_id}><input type={provider==='building_registry'?'radio':'checkbox'} name="external-record" aria-label={`수집 항목 ${record.external_id} 선택`} checked={selected.includes(record.external_id)} onChange={e=>{setAck(false);setSelected(values=>provider==='building_registry'?[record.external_id]:e.target.checked?[...values,record.external_id]:values.filter(id=>id!==record.external_id));}}/><span><strong>{record.name}</strong><small>{describeExternalFact(provider,record)}</small></span></label>)}</div>
     {provider==='building_registry'&&<><Field label="반영할 건물"><select value={buildingId} onChange={e=>{setBuildingId(e.target.value);setAck(false);}}>{exercise.subject.buildings.map(building=><option value={building.id} key={building.id}>{building.id} · {building.name}</option>)}</select></Field><fieldset className="external-fields"><legend>반영할 속성</legend>{[['floors','지상 층수'],['use','용도'],['name','건물명']].map(([id,name])=><label key={id}><input type="checkbox" checked={fields.includes(id)} onChange={e=>{setAck(false);setFields(values=>e.target.checked?[...values,id]:values.filter(value=>value!==id));}}/>{name}</label>)}</fieldset></>}
     {provider!=='weather'&&<p className="small muted">실제 공간자료는 위 대상물 설정에서 실제/혼합 모드를 명시해야 반영됩니다. 건물 치수·실내 구조와 용수 사용 가능 여부는 자동 검증되지 않습니다.</p>}
     <label className="check-label"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>출처·이용권·기준시각·좌표·선택 속성을 검토했고 훈련 초안에 반영합니다. 기관 정규 출시 승인이 아닙니다.</label>
     <Field label="기준자료 검토·정정 메모"><textarea value={note} onChange={e=>setNote(e.target.value)} maxLength={1000}/></Field>
     <button className="button primary" disabled={!ack||note.trim().length<3||!selected.length||provider==='building_registry'&&!fields.length} onClick={apply}><ShieldCheck size={15}/>검토한 항목을 초안에 반영</button>
    </div>}
   </fieldset>
   {exercise.published&&<p className="small muted">발행 당시 기준자료는 고정되어 있습니다. 변경은 새 편성 복제본에서 검토하세요.</p>}
   <ReferenceFacts subject={exercise.subject}/>
  </div>
 </section>;
}
