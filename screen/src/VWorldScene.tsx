import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import Scene,{type Props} from './Scene';
import {SiteMap} from './SiteMap';
import {mapViewport,validCamera,type CameraBridge} from './georeference';
import {kindNames} from './types';

export default function VWorldScene(props:Props){
 const frame=useRef<HTMLIFrameElement>(null),bridge=useRef(null) as CameraBridge;
 const current=useRef(props);current.current=props;
 const overlayFailed=useRef(false);
 const [frameUrl,setFrameUrl]=useState(''),[message,setMessage]=useState('브이월드 설정을 확인합니다.'),[ready,setReady]=useState(false),[retry,setRetry]=useState(0);
 const channel=useRef(crypto.randomUUID());
 const bootstrap=props.assetBase.startsWith('/api/screen/board/')?props.assetBase.replace(/\/assets\/$/,'/vworld'):'/api/screen/maps/vworld/bootstrap';
 const viewport=JSON.stringify(mapViewport(props.state,props.view));
 const send=()=>frame.current?.contentWindow?.postMessage({channel:channel.current,kind:'viewport',viewport:mapViewport(current.current.state,current.current.view)},'*');
 useEffect(()=>{send();},[viewport]);
 useEffect(()=>{
  let active=true;bridge.current=null;overlayFailed.current=false;setReady(false);setFrameUrl('');channel.current=crypto.randomUUID();
  const receive=(event:MessageEvent)=>{
   if(event.source!==frame.current?.contentWindow||event.origin!=='null'||event.data?.channel!==channel.current)return;
   if(event.data.kind==='map-frame-ready')send();
   else if(event.data.kind==='map-camera'&&validCamera(event.data.camera)){
    if(overlayFailed.current)return;
    bridge.current=event.data.camera;setReady(true);setMessage('브이월드3D · 훈련 위치/층·가림은 설정한 근사 형상 기준');
   }else if(event.data.kind==='map-error'){bridge.current=null;setReady(false);setMessage('브이월드에 연결하지 못했습니다. 키·등록 주소·인터넷·서비스 상태를 확인하세요.');}
  };
  addEventListener('message',receive);
  const timer=setTimeout(()=>{if(active&&!bridge.current){setReady(false);setMessage('브이월드 응답이 지연됩니다. 현재2D 배치를 유지합니다.');}},45000);
  void api<{frame_url:string;origin:string}>(bootstrap).then(config=>{
   if(!active)return;if(config.origin!==location.origin)throw Error(`인증키에 등록된 서비스 주소로 접속하세요: ${config.origin}`);
   if(!/^\/map-frame\.html(?:\?run_id=[A-Za-z0-9_-]+)?$/.test(config.frame_url))throw Error('지도 화면 주소를 확인하지 못했습니다.');
   setMessage('브이월드 지형·건물을 불러옵니다.');setFrameUrl(config.frame_url+'#channel='+channel.current);
  }).catch(error=>{if(active)setMessage(error instanceof Error?error.message:'브이월드 설정을 확인하세요.');});
  return()=>{active=false;clearTimeout(timer);removeEventListener('message',receive);bridge.current=null;};
 },[bootstrap,retry]);
 return <div className="scene-stage vworld-scene" data-renderer={ready?'vworld':'2d'}>
  {frameUrl&&<iframe ref={frame} className="vworld-map" title="브이월드3D 지도" src={frameUrl} sandbox="allow-scripts" referrerPolicy="origin"/>}
  {ready?<div className="vworld-overlay"><Scene {...props} bridge={bridge} onUnavailable={()=>{overlayFailed.current=true;bridge.current=null;setReady(false);setMessage('훈련3D를 표시할 수 없어 현재2D 배치를 유지합니다. 그래픽 설정을 확인한 뒤 다시 시도하세요.');}}/></div>:<div className="vworld-fallback"><SiteMap state={props.state}/><div><strong>브이월드 연결 준비 · 2D 현장 상태</strong><p>{message}</p><ul>{props.state.entities.filter(e=>e.visible).map(e=><li key={e.id}>{e.label} · {kindNames[e.kind]}{e.kind==='fire'?` · 연기 ${e.smoke}/화염 ${e.fire}`:''}</li>)}</ul><p>서버 터미널에서 <code>python -m screen.vworld configure --data-dir runtime/screen</code>으로 본인 발급 키를 숨김 입력하고 서버를 재시작하세요.</p><button onClick={()=>setRetry(v=>v+1)}>연결 다시 시도</button></div></div>}
  {ready&&<span className="asset-status vworld-caption" role="status">{message}</span>}
 </div>;
}
