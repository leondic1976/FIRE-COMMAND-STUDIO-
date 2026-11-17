import {useEffect,useRef,useState} from 'react';
import {Subject,StateValue,assetDisplayBuilding} from '../../../packages/domain-schemas';
import {LocalMap} from './components';
import {localToWGS84,rotateLocal} from '../../../packages/scene3d/coordinates';

interface Coordinate {getLat():number;getLng():number}
interface MapInstance {setCenter(position:Coordinate):void;relayout():void}
interface RoadviewInstance {setPanoId(id:number,position:Coordinate):void}
interface KakaoMaps {
 load(callback:()=>void):void;
 LatLng:new(lat:number,lng:number)=>Coordinate;
 Map:new(node:HTMLElement,options:{center:Coordinate;level:number})=>MapInstance;
 Polygon:new(options:Record<string,unknown>)=>{setMap(map:MapInstance):void};
 Marker:new(options:Record<string,unknown>)=>unknown;
 Roadview:new(node:HTMLElement)=>RoadviewInstance;
 RoadviewClient:new()=>{getNearestPanoId(position:Coordinate,radius:number,callback:(id:number|null)=>void):void};
 event:{addListener(target:unknown,event:string,callback:()=>void):void};
}
declare global {interface Window {kakao?:{maps:KakaoMaps}}}
let loading:Promise<KakaoMaps>|null=null;
const publicKey=import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY||'';
const approved=import.meta.env.VITE_KAKAO_MAPS_APPROVED==='true'&&/^[a-f0-9]{32}$/i.test(publicKey);

function loadSDK():Promise<KakaoMaps>{
 if(!approved)return Promise.reject(new Error('공식 SDK 이용 승인·JavaScript 키가 설정되지 않았습니다.'));
 if(window.kakao?.maps)return Promise.resolve(window.kakao.maps);
 if(loading)return loading;
 loading=new Promise((resolve,reject)=>{const script=document.createElement('script');let finished=false;const finish=(error?:Error)=>{if(finished)return;finished=true;clearTimeout(timeout);if(error){loading=null;script.remove();reject(error);}else if(window.kakao?.maps)resolve(window.kakao.maps);else reject(new Error('지도 SDK 응답을 확인할 수 없습니다.'));};const timeout=setTimeout(()=>finish(new Error('지도 SDK 연결이 지연되어 로컬 도식으로 유지합니다.')),7000);script.async=true;script.src=`https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(publicKey)}&autoload=false`;script.onerror=()=>finish(new Error('인터넷·도메인·키 설정을 확인하세요. 로컬 도식으로 훈련을 계속합니다.'));script.onload=()=>window.kakao?.maps.load(()=>finish());document.head.appendChild(script);});
 return loading;
}

function KakaoWidget({subject,selected,onSelect,roadview,onError}:{subject:Subject;selected:string;onSelect:(id:string)=>void;roadview:boolean;onError:(reason:string)=>void}){
 const root=useRef<HTMLDivElement>(null);const selectRef=useRef(onSelect);selectRef.current=onSelect;
 useEffect(()=>{let cancelled=false;let observer:ResizeObserver|undefined;let timeout:ReturnType<typeof setTimeout>|undefined;const node=root.current;if(!node)return;void loadSDK().then(maps=>{if(cancelled)return;const position=(x=0,z=0)=>{const [lat,lng]=localToWGS84(subject.latitude,subject.longitude,x,z);return new maps.LatLng(lat,lng);};const current=subject.buildings.map(b=>assetDisplayBuilding(subject,b)).find(b=>b.id===selected);const center=position(current?.x||0,current?.z||0);
  timeout=setTimeout(()=>{if(!cancelled)onError('외부 지도 응답을 확인하지 못했습니다. 로컬 도식으로 훈련을 계속합니다.');},7000);
  if(roadview){const viewer=new maps.Roadview(node),client=new maps.RoadviewClient();client.getNearestPanoId(center,50,id=>{if(cancelled)return;clearTimeout(timeout);if(!id){onError('주변에 제공되는 로드뷰가 없습니다. 로컬 도식으로 훈련을 계속합니다.');return;}viewer.setPanoId(id,center);});return;}
  const map=new maps.Map(node,{center,level:4});maps.event.addListener(map,'tilesloaded',()=>clearTimeout(timeout));for(const building of subject.buildings.map(b=>assetDisplayBuilding(subject,b))){const corners=building.footprint.length>=3?building.footprint:[[-building.width/2,-building.depth/2],[building.width/2,-building.depth/2],[building.width/2,building.depth/2],[-building.width/2,building.depth/2]];const path=corners.map(([x,z])=>{const [east,south]=rotateLocal(x,z,building.rotation+subject.north_rotation);return position(building.x+east,building.z+south);});const polygon=new maps.Polygon({path,strokeWeight:building.id===selected?3:2,strokeColor:building.id===selected?'#d88442':'#608eb2',strokeStyle:subject.target_mode==='VIRTUAL_ON_REAL_MAP'?'shortdash':'solid',fillColor:'#e5a469',fillOpacity:.22});polygon.setMap(map);maps.event.addListener(polygon,'click',()=>selectRef.current(building.id));}
  for(const f of subject.features.filter(f=>['HYDRANT','VEHICLE','ASSEMBLY'].includes(f.kind)))new maps.Marker({map,position:position(f.x,f.z),title:f.id+' · '+f.name});observer=new ResizeObserver(()=>map.relayout());observer.observe(node);
 }).catch(e=>{if(!cancelled)onError(e instanceof Error?e.message:'지도 표시 실패. 로컬 도식을 사용합니다.');});return()=>{cancelled=true;clearTimeout(timeout);observer?.disconnect();node.replaceChildren();};},[subject,selected,roadview]);
 return <div ref={root} className="kakao-widget" aria-label={roadview?'카카오 공식 로드뷰 위젯':'카카오 공식 지도 위젯'}/>;
}

export function MapView({subject,state,selected,onSelect}:{subject:Subject;state:Record<string,Record<string,StateValue>>;selected:string;onSelect:(id:string)=>void}){
 const [mode,setMode]=useState<'local'|'kakao'|'roadview'>('local'),[error,setError]=useState('');const available=approved&&subject.target_mode!=='VIRTUAL'&&subject.source.rights==='approved';
 useEffect(()=>{setMode('local');setError('');},[subject.id,subject.target_mode]);
 return <div className="map-view"><div className="map-provider-tabs"><button className={mode==='local'?'active':''} onClick={()=>{setMode('local');setError('');}}>로컬 도식</button><button disabled={!available} className={mode==='kakao'?'active':''} title={available?'공식 SDK로 표시':'실제/혼합 대상물·승인된 JavaScript 키 설정 필요'} onClick={()=>{setMode('kakao');setError('');}}>카카오 지도</button><button disabled={!available} className={mode==='roadview'?'active':''} title="공식 SDK 안에서만 참조·사진 추출 없음" onClick={()=>{setMode('roadview');setError('');}}>거리뷰</button></div>{mode==='local'?<LocalMap subject={subject} state={state} selected={selected} onSelect={onSelect}/>:<><KakaoWidget subject={subject} selected={selected} onSelect={onSelect} roadview={mode==='roadview'} onError={reason=>{setError(reason);setMode('local');}}/><div className="map-provider-note">{mode==='roadview'?'Kakao 공식 로드뷰 · 촬영 시점은 제공 위젯 참조':'Kakao 공식 지도 · 건물 윤곽은 근사 훈련 오버레이'}</div>{subject.target_mode==='VIRTUAL_ON_REAL_MAP'&&<div className="map-provider-note">실지도 + 존재하지 않는 가상 건물 · 점선 윤곽</div>}</>}{error&&<div className="map-provider-error" role="status">{error}</div>}{!available&&<div className="map-provider-note">외부 지도 승인·키 미설정 또는 가상 대상물 · 로컬 도식 사용</div>}</div>;
}
