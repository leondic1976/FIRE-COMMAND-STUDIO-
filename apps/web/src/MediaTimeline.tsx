import {useEffect,useMemo,useRef,useState} from 'react';
import {Expand,Volume2,VolumeX} from 'lucide-react';
import {AssetBinding,MediaCue,Message,SessionState,formatKST} from '../../../packages/domain-schemas';
import {mediaClock} from '../../../packages/domain-schemas/media-clock';
import {Badge,Field} from './components';
import {sessionElapsed} from './server-clock';
import './media.css';

interface Choice {key:string;binding:AssetBinding;cue:MediaCue;message:Message}
export function MediaTimeline({session,base}:{session:SessionState;base:string}){
 const [selected,setSelected]=useState('');
 const choices:Choice[]=session.messages.filter(message=>!message.reverted).flatMap(message=>(message.media_cues||[]).flatMap((cue,index)=>{const binding=session.subject.asset_bindings?.find(item=>item.id===cue.binding_id&&item.purpose==='VIDEO');return binding?[{key:message.event_seq+':'+index,binding,cue,message}]:[];}));
 const current=choices.find(item=>item.key===selected)||choices.at(-1);
 useEffect(()=>setSelected(''),[session.id]);
 if(!current)return null;
 return <section className="panel media-panel"><div className="panel-title"><div>사건 연계 영상 <Badge>훈련시계 동기</Badge></div></div><div className="padded"><Field label="표시할 사건 영상"><select value={current.key} onChange={e=>setSelected(e.target.value)}>{choices.map(item=><option value={item.key} key={item.key}>{item.message.id} · {item.binding.label}</option>)}</select></Field><VideoPlayback key={session.id+':'+current.key} choice={current} session={session} base={base}/></div></section>;
}

async function checkedVideo(url:string,sha256:string,signal:AbortSignal){
 const target=new URL(url,location.origin);if(target.origin!==location.origin||!target.pathname.startsWith('/api/v1/'))throw new Error('허용된 영상 경로가 아닙니다.');
 const response=await fetch(target,{credentials:'same-origin',cache:'no-store',signal});
 if(!response.ok||response.headers.get('content-type')?.split(';')[0]!=='video/webm')throw new Error('영상 접근 권한·검사·연결 상태를 확인하세요.');
 const limit=15*1024*1024;if(Number(response.headers.get('content-length')||0)>limit)throw new Error('영상 크기 제한을 초과했습니다.');
 if(!response.body)throw new Error('영상 응답이 비어 있습니다.');
 const reader=response.body.getReader(),chunks:Uint8Array[]=[];let size=0;
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw new Error('영상 크기 제한을 초과했습니다.');}chunks.push(value);}}finally{reader.releaseLock();}
 const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('');
 if(digest!==sha256)throw new Error('영상 무결성 검사를 통과하지 못했습니다.');
 return URL.createObjectURL(new Blob([bytes],{type:'video/webm'}));
}

function VideoPlayback({choice,session,base}:{choice:Choice;session:SessionState;base:string}){
 const {status,seq,state_version:version}=session;
 const {binding,cue,message}=choice,video=useRef<HTMLVideoElement>(null),frame=useRef<HTMLDivElement>(null);
 const [url,setUrl]=useState(''),[error,setError]=useState(''),[blocked,setBlocked]=useState(false),[muted,setMuted]=useState(true),[position,setPosition]=useState(cue.clip_start_seconds);
 const sample=useRef(session);sample.current=session;
 const isBlocked=useRef(false),failed=useRef(false),mounted=useRef(true);
 const query=status==='REPLAY'?'?seq='+seq:'';
 const content=useMemo(()=>`${base}/${binding.asset_id}/content${query}`,[base,binding.asset_id,query]);
 useEffect(()=>{const abort=new AbortController();let blob='';setUrl('');setError('');failed.current=false;isBlocked.current=false;setBlocked(false);mounted.current=true;
  void checkedVideo(content,binding.sha256,abort.signal).then(value=>{blob=value;if(abort.signal.aborted)URL.revokeObjectURL(value);else setUrl(value);}).catch(reason=>{if(!abort.signal.aborted)setError(reason instanceof Error?reason.message:'영상 로딩 실패');});
  return()=>{mounted.current=false;abort.abort();video.current?.pause();if(blob)URL.revokeObjectURL(blob);};},[content,binding.sha256]);
 useEffect(()=>{if(!url)return;const synchronize=()=>{const element=video.current;if(!element||element.readyState<1||failed.current)return;const clock=sample.current;const value=mediaClock(cue,message.simulated_seconds,sessionElapsed(clock),clock.status);setPosition(value.target);
   if(Math.abs(element.currentTime-value.target)>.35)element.currentTime=value.target;
   if(value.playing){if(element.paused&&!isBlocked.current)void element.play().catch(()=>{if(mounted.current&&video.current?.src===url){isBlocked.current=true;setBlocked(true);}});}else element.pause();
  };synchronize();const timer=setInterval(synchronize,200);return()=>clearInterval(timer);},[url,cue.clip_start_seconds,cue.clip_end_seconds,message.simulated_seconds]);
 const allowPlayback=()=>{const element=video.current;if(!element)return;isBlocked.current=false;setBlocked(false);void element.play().catch(()=>{isBlocked.current=true;setBlocked(true);});};
 return <div className="video-playback" data-video-binding={binding.id} data-media-seq={seq} data-media-version={version}><div className="media-frame" ref={frame}>{url&&<video ref={video} src={url} muted={muted} playsInline preload="auto" disablePictureInPicture disableRemotePlayback aria-label={binding.label+' · 훈련시계 동기 영상'} onLoadedMetadata={()=>{const element=video.current;if(!element)return;if(!Number.isFinite(element.duration)||Math.abs(element.duration-(binding.manifest.duration_seconds||0))>1){failed.current=true;element.pause();setError('영상 길이와 승인 매니페스트가 다릅니다.');}}} onError={()=>{failed.current=true;setError('이 브라우저에서 영상을 재생하지 못했습니다.3D·메시지로 훈련을 계속할 수 있습니다.');}}/>}<div className="media-watermark">훈련용 · 촬영/합성 기준자료<br/>실시간 현장·공학 예측 아님</div>{!url&&!error&&<p className="media-placeholder" role="status">검토 영상 무결성 확인 중…</p>}</div>
 {error&&<p className="alert error" role="alert">{error}</p>}{blocked&&<button className="button" onClick={allowPlayback}>동기 영상 재생 허용</button>}<div className="media-transport"><span role="status">{status==='RUNNING'?(position>=cue.clip_end_seconds-.03?'클립 종료':'훈련시계에 맞춰 재생'):status==='REPLAY'?'기록 시점 정지 화면':'훈련 정지 · 영상 정지'} · {position.toFixed(1)} / {cue.clip_end_seconds.toFixed(1)}초</span><button className="icon-button" aria-label={muted?'영상 소리 켜기':'영상 음소거'} onClick={()=>setMuted(value=>!value)}>{muted?<VolumeX size={15}/>:<Volume2 size={15}/>}</button><button className="icon-button" aria-label="영상 전체화면" onClick={()=>void frame.current?.requestFullscreen().catch(()=>{})}><Expand size={15}/></button></div>
 <p className="media-caption"><strong>{message.id} · {cue.feature_id}</strong><br/>{binding.source.classification==='SYNTHETIC'?'합성 영상 · 실제 시설과 무관':'촬영 영상 · 현재 현장 보증 아님'}<br/>원천 {binding.source.provider} · 자료 기준 {binding.source.as_of}<br/>사건 공개 {formatKST(message.at)} · SEQ {seq} / v{version}<br/>음성·픽셀의 익명화와 실제 시설 정확도는 사람의 검토 범위입니다.</p></div>;
}
