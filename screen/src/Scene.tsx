import {useEffect,useRef,useState} from 'react';
import * as T from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {batchStatic,box,disposeTree,label,makeBuilding,makeEntity,makeWorld,material} from './world';
import {FireEffect,WaterEffect,RainEffect} from './effects';
import {entityPosition,kindNames,type Entity,type SceneState,type Side} from './types';
import {SiteMap} from './SiteMap';

export type View=Side|'overview'|'commander';
type Props={state:SceneState;view:View;low:boolean;phase:string;assetBase:string;onStats?:(fps:number,calls:number)=>void};
type Visual={group:T.Group;entity:Entity;fire?:FireEffect;water?:WaterEffect;wave?:T.Object3D};


export default function Scene(props:Props){
 const node=useRef<HTMLDivElement>(null),current=useRef(props),update=useRef<((value:Props)=>void)|null>(null);
 const savedCamera=useRef<{position:T.Vector3;target:T.Vector3;view:string;signature:string}|null>(null);
 const [fallback,setFallback]=useState(false),[retry,setRetry]=useState(0),[assetMessage,setAssetMessage]=useState('');
 current.current=props;
 useEffect(()=>{update.current?.(props);},[props.state,props.view,props.phase,props.assetBase]);
 useEffect(()=>{
  const host=node.current;if(!host||fallback)return;
  let active=true,frame=0,renderer:T.WebGLRenderer;
  try{renderer=new T.WebGLRenderer({antialias:!props.low,alpha:false,powerPreference:'high-performance'});}catch{setFallback(true);return;}
  renderer.setPixelRatio(Math.min(devicePixelRatio,props.low?.9:1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
  renderer.domElement.setAttribute('aria-label','가상 현장 3D 영상. 드래그로 회전, 휠로 확대합니다. 상단 버튼으로 A B C D 방면을 선택할 수 있습니다.');renderer.domElement.setAttribute('role','img');host.appendChild(renderer.domElement);
  const scene=new T.Scene();scene.background=new T.Color('#d9e5eb');scene.fog=new T.Fog('#d9e5eb',160,420);
  const hemi=new T.HemisphereLight('#e6f2ff','#79836b',2.8);scene.add(hemi);
  const sun=new T.DirectionalLight('#fff3db',3.5);sun.position.set(-50,100,65);sun.castShadow=true;sun.shadow.mapSize.setScalar(props.low?1024:2048);Object.assign(sun.shadow.camera,{left:-140,right:140,top:140,bottom:-140,far:260});sun.shadow.bias=-.0004;sun.shadow.normalBias=.04;scene.add(sun);
  const camera=new T.PerspectiveCamera(42,1,.3,700);camera.position.set(65,25,105);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.maxPolarAngle=Math.PI/2.03;controls.minDistance=13;controls.maxDistance=320;controls.target.set(0,7,0);
  const rain=new RainEffect(props.low);scene.add(rain.group);
  const clock=new T.Clock(),reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let dirty=true;controls.addEventListener('change',()=>{dirty=true;});
  let world=new T.Group(),signature='',lastView='',elapsedEffects=0,lastTime=0,statTime=0,statFrames=0;
  let abort=new AbortController();const visuals=new Map<string,Visual>(),buildingGroups=new Map<string,T.Group>();
  const move=(view:View,state:SceneState)=>{const rotation=(state.site.front_bearing-180)*Math.PI/180;const height=Math.max(10,state.buildings[0].floors*state.buildings[0].floor_height);const positions:Record<View,[number,number,number]>={A:[42,Math.max(17,height*.85),112],B:[-88,Math.max(12,height*.7),-23],C:[-28,Math.max(12,height*.7),-88],D:[88,Math.max(12,height*.7),25],overview:[108,100,120],commander:[5,2.2,74]};camera.position.set(...positions[view]).applyAxisAngle(new T.Vector3(0,1,0),rotation);controls.target.set(state.buildings[0].x,height*.45,state.buildings[0].z).applyAxisAngle(new T.Vector3(0,1,0),rotation);controls.update();};
  const rebuild=(value:Props)=>{
   const nextSignature=JSON.stringify([value.state.buildings,value.state.site.front_bearing,value.assetBase]);
   if(nextSignature!==signature){
    abort.abort();abort=new AbortController();scene.remove(world);disposeTree(world);visuals.clear();buildingGroups.clear();
    const built=makeWorld(value.state);world=built.group;world.rotation.y=(value.state.site.front_bearing-180)*Math.PI/180;scene.add(world);signature=nextSignature;lastView='';setAssetMessage('');
    for(const building of value.state.buildings){
     const generated=makeBuilding(building);world.add(generated);buildingGroups.set(building.id,generated);
     if(building.model_asset_id){
      if(value.state.site.target_mode==='REAL')generated.visible=false;
      const controller=abort;setAssetMessage('승인된 3D 자료를 불러오는 중');
      void fetch(value.assetBase+encodeURIComponent(building.model_asset_id)+(value.assetBase==='/api/screen/assets/'?'/content':''),{signal:controller.signal,credentials:'same-origin'}).then(response=>{if(!response.ok)throw Error('Model');return response.arrayBuffer();}).then(data=>new GLTFLoader().parseAsync(data,'')).then(gltf=>{
       if(!active||controller.signal.aborted){disposeTree(gltf.scene);return;}
       const bounds=new T.Box3().setFromObject(gltf.scene),center=bounds.getCenter(new T.Vector3());gltf.scene.position.set(building.x-center.x,-bounds.min.y,building.z-center.z);gltf.scene.traverse(o=>{const m=o as T.Mesh;if(m.isMesh){m.castShadow=true;m.receiveShadow=true;}});world.add(gltf.scene);generated.visible=false;setAssetMessage('승인 모델 표시 · 위치/정확도 라벨 확인');
      }).catch(error=>{if(!active||controller.signal.aborted||error?.name==='AbortError')return;if(value.state.site.target_mode==='REAL'){setAssetMessage('실제 모델 표시 실패 · 2D 배치도만 표시합니다.');setFallback(true);}else setAssetMessage('모델 표시 실패 · 근사 형상으로 표시');});
     }
     for(const [side,asset]of Object.entries(building.facade_assets)){
      const controller=abort;void fetch(value.assetBase+encodeURIComponent(asset!)+(value.assetBase==='/api/screen/assets/'?'/content':''),{signal:controller.signal,credentials:'same-origin'}).then(r=>{if(!r.ok)throw Error('Photo');return r.blob();}).then(blob=>createImageBitmap(blob,{imageOrientation:'flipY'})).then(bitmap=>{if(!active||controller.signal.aborted){bitmap.close();return;}const tex=new T.Texture(bitmap);tex.colorSpace=T.SRGBColorSpace;tex.flipY=false;tex.needsUpdate=true;const w=side==='A'||side==='C'?building.width:building.depth,h=building.floors*building.floor_height;const plane=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshStandardMaterial({map:tex,roughness:.85}));plane.position.set(building.x,h/2,building.z);if(side==='A')plane.position.z+=building.depth/2+.13;else if(side==='C'){plane.position.z-=building.depth/2+.13;plane.rotation.y=Math.PI;}else if(side==='B'){plane.position.x-=building.width/2+.13;plane.rotation.y=-Math.PI/2;}else{plane.position.x+=building.width/2+.13;plane.rotation.y=Math.PI/2;}world.add(plane);}).catch(()=>{if(active&&!controller.signal.aborted)setAssetMessage('일부 사진 표시 실패 · 기본 재질 유지');});
     }
    }
    batchStatic(world);
   }
   if(value.view!==lastView){move(value.view,value.state);lastView=value.view;}
   const ids=new Set(value.state.entities.map(e=>e.id));for(const [id,v]of visuals)if(!ids.has(id)){world.remove(v.group);disposeTree(v.group);if(v.water){world.remove(v.water.group);disposeTree(v.water.group);}visuals.delete(id);}
   for(const entity of value.state.entities){
    let visual=visuals.get(entity.id);
    if(!visual){const group=makeEntity(entity);batchStatic(group);visual={group,entity};if(entity.kind==='fire'){visual.fire=new FireEffect(value.low);group.add(visual.fire.group);}if(entity.kind==='engine'){visual.water=new WaterEffect();world.add(visual.water.group);}if(entity.kind==='victim'){const tag=label('요구조자','#ac5d81',7);tag.position.y=3;group.add(tag);}group.position.set(...entityPosition(entity,value.state.buildings));world.add(group);visuals.set(entity.id,visual);}
    visual.entity=entity;visual.group.visible=entity.visible;
    if(entity.kind==='victim'){const tag=visual.group.children.find(c=>c instanceof T.Sprite);if(tag)tag.visible=entity.status!=='rescued';}
   }
   renderer.shadowMap.needsUpdate=true;dirty=true;
   for(const building of buildingGroups.values()){const windows=building.getObjectByName('windows') as T.InstancedMesh|undefined;if(windows){const mat=windows.material as T.MeshStandardMaterial;mat.emissive.set('#789ba6');mat.emissiveIntensity=value.state.power?.12:0;}}
   for(const b of value.state.buildings){const g=buildingGroups.get(b.id),level=value.state.damage[b.id]||0;if(g&&level&&!g.getObjectByName('debris')){const debris=new T.Group();debris.name='debris';const mat=material('#8c8173');for(let i=0;i<18;i++){const piece=box(debris,.2+(i%3)*.2,.18,.3+(i%4)*.2,mat,-b.width/2-1-(i%4),.18,(i/18-.5)*b.depth);piece.rotation.set(i*.2,i,i*.4);}g.add(debris);}const roof=g?.getObjectByName('roof');if(roof){roof.rotation.z=level>=2?.05*level:0;roof.visible=level<3;}}
  };
  update.current=rebuild;rebuild(props);if(savedCamera.current?.signature===signature&&savedCamera.current.view===lastView){camera.position.copy(savedCamera.current.position);controls.target.copy(savedCamera.current.target);controls.update();}
  const resize=()=>{const {width,height}=host.getBoundingClientRect();if(width<1||height<1)return;renderer.setSize(width,height,false);dirty=true;camera.aspect=width/height;camera.updateProjectionMatrix();};const observer=new ResizeObserver(resize);observer.observe(host);resize();
  const lost=(event:Event)=>{event.preventDefault();if(active)setFallback(true);};renderer.domElement.addEventListener('webglcontextlost',lost);
  const animate=()=>{
   if(!active)return;frame=requestAnimationFrame(animate);const now=clock.getElapsedTime(),dt=Math.min(.1,now-lastTime);lastTime=now;const value=current.current;if(value.phase!=='PAUSED'&&!reduced)elapsedEffects+=dt;
   const state=value.state;rain.update(elapsedEffects,state.weather.rain);sun.intensity=3.5*state.weather.daylight;hemi.intensity=1.8+state.weather.daylight;(scene.fog as T.Fog).near=160-state.weather.fog*90;(scene.fog as T.Fog).far=420-state.weather.fog*180;
   for(const visual of visuals.values()){
    const entity=visual.entity;const target=new T.Vector3(...entityPosition(entity,state.buildings));visual.group.position.lerp(target,reduced?1:Math.min(1,dt*2));visual.group.rotation.y=entity.heading*Math.PI/180;
    visual.fire?.update(entity,elapsedEffects,camera,state.weather,renderer.domElement.clientHeight);
    const wave=visual.group.getObjectByName('wave');if(wave&&entity.kind==='victim')wave.rotation.z=entity.status==='rescued'?-.2:2.3+Math.sin(elapsedEffects*3)*.35;
    const beacon=visual.group.getObjectByName('beacon')as T.Mesh|undefined;if(beacon)(beacon.material as T.MeshStandardMaterial).emissiveIntensity=reduced?.6:(Math.sin(elapsedEffects*5)>0?1.5:.15);
    const ladder=visual.group.getObjectByName('ladder');if(ladder){const destination=state.entities.find(e=>e.id===entity.target_id);if(entity.status==='active'&&destination){const target=new T.Vector3(...entityPosition(destination,state.buildings)).sub(visual.group.position);const distance=Math.hypot(target.x,target.z);ladder.rotation.y=-Math.atan2(target.z,target.x)-visual.group.rotation.y;ladder.rotation.z=T.MathUtils.clamp(Math.atan2(target.y-2.7,distance),.12,1.3);ladder.scale.x=T.MathUtils.clamp(distance/10,1,2.5);}else{ladder.rotation.set(0,0,.08);ladder.scale.x=1;}}
    if(visual.water){const destination=state.entities.find(e=>e.id===entity.target_id);visual.water.group.visible=entity.visible&&entity.spraying&&entity.status!=='unavailable'&&state.water&&!!destination;if(destination)visual.water.update(elapsedEffects,visual.group.position,new T.Vector3(...entityPosition(destination,state.buildings)));}
   }
   controls.update();if(value.phase!=='PAUSED'||dirty){renderer.render(scene,camera);dirty=false;statFrames++;}if(now-statTime>=2){const fps=Math.round(statFrames/(now-statTime));value.onStats?.(fps,renderer.info.render.calls);if(value.low&&fps<22&&value.phase!=='PAUSED'&&renderer.getPixelRatio()>.66){renderer.setPixelRatio(Math.max(.65,renderer.getPixelRatio()-.1));resize();}statTime=now;statFrames=0;}
  };animate();
  return()=>{savedCamera.current={position:camera.position.clone(),target:controls.target.clone(),view:lastView,signature};active=false;abort.abort();cancelAnimationFrame(frame);observer.disconnect();controls.dispose();renderer.domElement.removeEventListener('webglcontextlost',lost);update.current=null;disposeTree(scene);renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();};
 },[props.low,retry,fallback]);
 return <div className="scene-stage" data-renderer={fallback?'2d':'3d'}>
  {!fallback?<div className="webgl-host" ref={node}/>:<div className="fallback-scene"><SiteMap state={props.state}/><div><strong>2D 현장 상태</strong><p>3D를 사용할 수 없어 현재 배치와 상황을 표시합니다.</p><ul>{props.state.entities.filter(e=>e.visible).map(e=><li key={e.id}>{e.label} · {kindNames[e.kind]}{e.kind==='fire'?` · 연기 ${e.smoke}/화염 ${e.fire}`:''}</li>)}</ul><button onClick={()=>{setFallback(false);setRetry(n=>n+1);}}>3D 다시 시도</button></div></div>}
  {assetMessage&&<span className="asset-status" role="status">{assetMessage}</span>}
 </div>;
}
