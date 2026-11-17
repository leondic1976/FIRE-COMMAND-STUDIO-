import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {Subject,StateValue,assetDisplayBuilding} from '../domain-schemas';
import {sceneStateSummary} from './state-summary';
import {disposeAsset,loadAssetModel,loadAssetTexture} from './asset-runtime';
import {proceduralBuilding,proceduralInterior,proceduralSiteResource} from './procedural-building';
import {floorElevation,interiorKinds,sceneObjectBudget,siteRadius} from '../domain-schemas/building-plan';
import './scene-summary.css';

export interface SceneProps {subject:Subject; state:Record<string,Record<string,StateValue>>; selected:string; onSelect:(id:string)=>void; hiddenFloor:number;cutaway?:boolean; exploded:boolean; cameraView:string; resetKey:number;assetBase?:string; onPerformance?:(fps:number,triangles:number,quality:string)=>void}
export function Scene(props:SceneProps) {
  const host=useRef<HTMLDivElement>(null);
  const [failed,setFailed]=useState(false);
  const [assetStates,setAssetStates]=useState<Record<string,string>>({}),[objectInfo,setObjectInfo]=useState('');
  const assetCache=useRef(new Map<string,ArrayBuffer>());
  useEffect(()=>()=>assetCache.current.clear(),[]);
  const savedView=useRef<{position:THREE.Vector3;target:THREE.Vector3;view:string;reset:number;assets:string}|null>(null);
  const onSelect=useRef(props.onSelect); onSelect.current=props.onSelect;
  const onPerf=useRef(props.onPerformance); onPerf.current=props.onPerformance;
  useEffect(()=>{
    const node=host.current;if(!node||failed)return;
    const assetController=new AbortController(),bindings=(props.subject.asset_bindings||[]).filter(binding=>binding.purpose==='MODEL'||binding.purpose==='FACADE'),assetSignature=bindings.map(binding=>binding.id+binding.sha256).join('|');
    const allowedCache=new Set(bindings.map(binding=>`${props.assetBase}/${binding.asset_id}/content#${binding.sha256}`));
    for(const key of assetCache.current.keys())if(!allowedCache.has(key))assetCache.current.delete(key);
    setAssetStates({});setObjectInfo('');
    const estimatedObjects=sceneObjectBudget(props.subject.buildings,props.subject.features,props.state);
    if(estimatedObjects>15000){onPerf.current?.(0,0,'2D · 장면 예산 초과');setFailed(true);return;}
    let renderer:THREE.WebGLRenderer;
    try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});}catch{setFailed(true);return;}
    const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.setClearColor('#16202c');renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
    renderer.domElement.setAttribute('aria-label','훈련 대상물 3D 장면. 드래그로 회전, 스크롤로 확대. 키보드 조작은 상단 시점 버튼을 사용하세요.');renderer.domElement.setAttribute('role','img');node.appendChild(renderer.domElement);
    const scene=new THREE.Scene();scene.fog=new THREE.Fog('#16202c',170,350);
    scene.add(new THREE.HemisphereLight('#e4eff8','#4b5b61',2.4));
    const sun=new THREE.DirectionalLight('#ffe6c0',3.5);sun.position.set(-65,95,65);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-110;sun.shadow.camera.right=110;sun.shadow.camera.top=110;sun.shadow.camera.bottom=-110;sun.shadow.camera.far=260;sun.shadow.bias=-0.001;scene.add(sun);
    const camera=new THREE.PerspectiveCamera(37,1,0.5,700);
    const views:Record<string,number[]>={overview:[115,95,135],north:[0,48,-145],top:[0,170,0.1],street:[75,22,85]};const v=views[props.cameraView]||views.overview;camera.position.set(v[0],v[1],v[2]);
    const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,3,0);controls.enableDamping=!reduced;controls.maxPolarAngle=Math.PI/2.03;controls.minDistance=25;controls.maxDistance=280;controls.update();
    const extent=Math.max(90,siteRadius(props.subject,props.state),...props.subject.buildings.map(b=>Math.max(Math.abs(b.x)+b.width,Math.abs(b.z)+b.depth)),...props.subject.features.filter(f=>!f.building_id).map(f=>Math.max(Math.abs(f.x)+8,Math.abs(f.z)+8)),...bindings.filter(binding=>binding.purpose==='MODEL').map(binding=>{const b=props.subject.buildings.find(value=>value.id===binding.building_id);return Math.max(Math.abs(b?.x||0),Math.abs(b?.z||0))+(Math.max(...[0,1,2].map(i=>binding.manifest.bounds[1][i]-binding.manifest.bounds[0][i]))*binding.unit_scale)+Math.max(Math.abs(binding.offset[0]),Math.abs(binding.offset[2]));}));
    controls.target.y=Math.max(3,...props.subject.buildings.map(b=>b.floors*b.floor_height/3),...bindings.filter(binding=>binding.purpose==='MODEL').map(binding=>(binding.manifest.bounds[1][1]-binding.manifest.bounds[0][1])*binding.unit_scale/3+binding.offset[1]));controls.update();
    if(extent>100){camera.position.multiplyScalar(extent/90);camera.far=extent*8;camera.updateProjectionMatrix();controls.maxDistance=extent*4;scene.fog=new THREE.Fog('#16202c',extent*2,extent*6);}
    if(savedView.current?.view===props.cameraView&&savedView.current.reset===props.resetKey&&savedView.current.assets===assetSignature){camera.position.copy(savedView.current.position);controls.target.copy(savedView.current.target);controls.update();}
    const mat=(color:string,roughness=0.8,metalness=0)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
    const mesh=(geometry:THREE.BufferGeometry,material:THREE.Material,position:number[],parent:THREE.Object3D=scene)=>{const m=new THREE.Mesh(geometry,material);m.position.set(position[0],position[1],position[2]);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;};
    const box=(x:number,y:number,z:number,color:string,pos:number[],parent:THREE.Object3D=scene)=>mesh(new THREE.BoxGeometry(x,y,z),mat(color),pos,parent);
    const ground=box(Math.max(225,extent*2.2),0.5,Math.max(160,extent*2.2),'#5c6a68',[0,-0.5,0]);ground.castShadow=false;
    if(props.hiddenFloor<0){const material=ground.material as THREE.MeshStandardMaterial;material.transparent=true;material.opacity=.12;material.depthWrite=false;}
    if(props.subject.target_mode==='VIRTUAL'){
    box(225,0.12,16,'#29333d',[0,0,31]);box(13,0.13,160,'#29333d',[31,0.01,0]);box(225,0.12,12,'#29333d',[0,0,-38]);
    for(let x=-100;x<110;x+=10)box(4,0.02,0.25,'#c1b892',[x,0.11,31]);
    for(let z=-65;z<75;z+=10)box(0.25,0.02,4,'#c1b892',[31,0.12,z]);
    box(44,0.1,22,'#778380',[-49,0,13]);
    for(let x=-66;x<-32;x+=7)box(0.15,0.02,9,'#c2ccc7',[x,0.12,16]);
    }
    const textures:THREE.Texture[]=[];
    function label(text:string,color='#f4f8fb',scale=15){const c=document.createElement('canvas');c.width=512;c.height=96;const ctx=c.getContext('2d')!;ctx.fillStyle='rgba(13,21,31,.88)';ctx.roundRect(0,0,512,96,14);ctx.fill();ctx.font='bold 29px "Malgun Gothic",sans-serif';ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText(text,256,61);const t=new THREE.CanvasTexture(c);textures.push(t);const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:t,depthTest:false}));sprite.scale.set(scale,scale*96/512,1);return sprite;}
    for(const b of props.subject.buildings){
      const group=new THREE.Group();const spread=props.exploded?1.35:1;group.position.set(b.x*spread,0,b.z*spread);group.rotation.y=THREE.MathUtils.degToRad(b.rotation+props.subject.north_rotation);scene.add(group);
      const selected=b.id===props.selected;
      const entranceClosed=props.subject.features.filter(f=>f.building_id===b.id&&f.kind==='ENTRANCE').some(f=>props.state[f.id]?.closed);
      const structure=proceduralBuilding(b,{hiddenFloor:props.hiddenFloor,cutaway:props.cutaway,selected,closed:entranceClosed});group.add(structure);
      const topFloor=props.hiddenFloor?Math.min(b.floors,props.hiddenFloor):b.floors,roofY=topFloor<0?(topFloor+1)*b.floor_height:topFloor*b.floor_height;
      for(const feature of props.subject.features.filter(f=>f.building_id===b.id&&(!props.hiddenFloor||f.floor<=props.hiddenFloor))){
        const st=props.state[feature.id]||feature.state,interior=proceduralInterior(feature,b,st);if(interior)group.add(interior);if(feature.kind==='ENTRANCE'){const entrance=proceduralSiteResource(feature,st);if(entrance)group.add(entrance);}
        if(feature.floor===0)continue;
        const effects=new THREE.Group();effects.position.set(feature.x+(feature.kind in interiorKinds?0:-5),floorElevation(feature.floor,b.floor_height),feature.z+(feature.kind in interiorKinds?0:-b.depth/2-.4));group.add(effects);effects.userData.featureId=feature.id;
        const smoke=Math.min(4,Math.max(0,Number(st.smoke)||0)),fire=Math.min(4,Math.max(0,Number(st.fire)||0));
        for(let i=0;i<smoke*4;i++){const sm=new THREE.Mesh(new THREE.SphereGeometry(1.3+i*.18,9,7),new THREE.MeshStandardMaterial({color:'#59636a',transparent:true,opacity:.22+smoke*.055,depthWrite:false}));sm.position.set(Math.sin(i*2)*2.4,b.floor_height+1+i*.8,-Math.cos(i)*2);sm.scale.set(1.4,1,1.2);effects.add(sm);}
        if(fire){const flame=mesh(new THREE.ConeGeometry(1.1+fire*.2,fire*1.8,7),new THREE.MeshBasicMaterial({color:'#f6a33e',transparent:true,opacity:.9}),[0,b.floor_height*.65,0],effects);flame.rotation.z=-.1;}
      }
      const buildingState=props.state[b.id]||{};if(buildingState.warning){const ring=mesh(new THREE.RingGeometry(Math.max(b.width,b.depth)*.7,Math.max(b.width,b.depth)*.7+.7,64),new THREE.MeshBasicMaterial({color:'#f7a44c',side:THREE.DoubleSide}),[0,.18,0],group);ring.rotation.x=-Math.PI/2;}
      const accuracy=b.accuracy==='VERIFIED'?'검증 범위 확인':b.accuracy==='APPROXIMATE'?'근사':'가상';
      const title=label(`${b.id}  ${b.name} · ${accuracy}`,selected?'#ffb565':'#eef4f6',20);const imported=bindings.find(binding=>binding.building_id===b.id&&binding.purpose==='MODEL');title.position.set(imported?.offset[0]||0,Math.max(roofY,imported?(imported.manifest.bounds[1][1]-imported.manifest.bounds[0][1])*imported.unit_scale+imported.offset[1]:0)+5,imported?.offset[2]||0);group.add(title);
      for(const feature of props.subject.features.filter(f=>f.building_id===b.id&&f.floor===0&&f.kind==='ZONE')){
        const water=Math.min(20,Math.max(0,Number((props.state[feature.id]||feature.state).water)||0));
        if(water>0){const marker=mesh(new THREE.CircleGeometry(4+water,32),new THREE.MeshBasicMaterial({color:'#5dadd3',transparent:true,opacity:.5,side:THREE.DoubleSide}),[feature.x,.2,feature.z],group);marker.rotation.x=-Math.PI/2;const tag=label(`${feature.id} 침수 ${water}단계 (연출)`,'#a2d5f2',22);tag.position.set(feature.x,3,feature.z);group.add(tag);}
      }
      for(const binding of bindings.filter(value=>value.building_id===b.id&&value.purpose!=='REFERENCE')){
        if(!props.assetBase){setAssetStates(values=>({...values,[binding.id]:'승인 자산 경로 없음 · 근사 모델'}));continue;}
        const url=`${props.assetBase}/${binding.asset_id}/content`;
        setAssetStates(values=>({...values,[binding.id]:'로딩 중'}));
        if(binding.purpose==='MODEL')void loadAssetModel(url,binding.sha256,assetController.signal,assetCache.current).then(result=>{
          if(assetController.signal.aborted){disposeAsset(result.root);return;}
          if(result.nodes.size!==binding.manifest.nodes.length||binding.manifest.nodes.some(node=>!result.nodes.has(node.index))){disposeAsset(result.root);throw new Error('객체 매핑 불일치');}
          const bounds=binding.manifest.bounds,placement=new THREE.Group(),normalized=new THREE.Group();
          placement.position.fromArray(binding.offset);placement.rotation.y=THREE.MathUtils.degToRad(binding.rotation_y);
          normalized.scale.setScalar(binding.unit_scale);normalized.position.set(-(bounds[0][0]+bounds[1][0])/2*binding.unit_scale,-bounds[0][1]*binding.unit_scale,-(bounds[0][2]+bounds[1][2])/2*binding.unit_scale);
          result.nodes.forEach((object,index)=>{const floor=binding.floor_map[index]||0;object.visible=!props.hiddenFloor||!floor||floor<=props.hiddenFloor;
            if(props.exploded&&floor)object.position.y=(floor-1)*1.2/binding.unit_scale;
            object.traverse(child=>{if(child instanceof THREE.Mesh){child.userData.buildingId=b.id;const featureId=binding.object_map[index],state=featureId?props.state[featureId]:undefined;const restricted=state?.closed||state?.warning;
              child.userData.assetNode=`${binding.label} / ${index} · ${binding.manifest.nodes.find(value=>value.index===index)?.name||'객체'} / ${floor?floor+'층':'외관 전체'}${restricted?' · 통제/위험 연출':''}`;
              if(restricted)for(const material of Array.isArray(child.material)?child.material:[child.material])if(material instanceof THREE.MeshStandardMaterial){material.color.set('#d07a50');material.emissive.set('#421c0d');}
            }});
          });
          normalized.add(result.root);placement.add(normalized);group.add(placement);structure.visible=false;if(selected){scene.updateMatrixWorld(true);scene.add(new THREE.BoxHelper(placement,'#eab37c'));}
          // Anchors use the reviewed object's actual geometry bounds. Visual
          // smoke/flame stays explicitly illustrative, never a simulation result.
          for(const [index,featureId] of Object.entries(binding.object_map)){
            const nodeBounds=binding.manifest.nodes.find(value=>String(value.index)===index)?.bounds;if(!nodeBounds)continue;
            const anchor=new THREE.Vector3((nodeBounds[0][0]+nodeBounds[1][0])/2,nodeBounds[1][1],(nodeBounds[0][2]+nodeBounds[1][2])/2);
            anchor.multiplyScalar(binding.unit_scale).add(normalized.position).applyAxisAngle(new THREE.Vector3(0,1,0),THREE.MathUtils.degToRad(binding.rotation_y)).add(new THREE.Vector3().fromArray(binding.offset));
            if(props.exploded&&binding.floor_map[index])anchor.y+=(binding.floor_map[index]-1)*1.2;
            const effect=group.children.find(value=>value.userData.featureId===featureId);if(effect){effect.position.copy(anchor);for(const child of effect.children)child.position.y-=b.floor_height*.65; }
          }
          setAssetStates(values=>({...values,[binding.id]:`${binding.label} · 모델 표시 · ${result.nodes.size}객체 · ${Array.from(result.nodes.values()).filter(value=>value.visible).length}객체 표시 · ${binding.visibility==='PUBLIC'?'공동 공개':'진행·평가 전용'}`}));
        }).catch(()=>{if(!assetController.signal.aborted)setAssetStates(values=>({...values,[binding.id]:'모델 로딩 실패 · 근사 모델로 대체'}));});
        else void loadAssetTexture(url,binding.sha256,assetController.signal,assetCache.current).then(texture=>{
          const side=['EAST','WEST'].includes(binding.photo_face),height=b.floors*b.floor_height,width=side?b.depth:b.width;
          const plane=mesh(new THREE.PlaneGeometry(width,height),new THREE.MeshStandardMaterial({map:texture,roughness:.85,metalness:0,side:THREE.DoubleSide}),[0,height/2,0],structure);
          if(binding.photo_face==='NORTH'){plane.position.z=-b.depth/2-.2;plane.rotation.y=Math.PI;}else if(binding.photo_face==='SOUTH')plane.position.z=b.depth/2+.2;else{plane.position.x=(binding.photo_face==='EAST'?1:-1)*(b.width/2+.2);plane.rotation.y=binding.photo_face==='EAST'?Math.PI/2:-Math.PI/2;}
          setAssetStates(values=>({...values,[binding.id]:`${binding.label} · 사진 색상맵 · 물성/다른 면은 근사`}));
        }).catch(()=>{if(!assetController.signal.aborted)setAssetStates(values=>({...values,[binding.id]:'외벽 사진 로딩 실패 · 기본 재질로 대체'}));});
      }
      if(selected){const edges=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(b.width+1,b.floors*b.floor_height+.6,b.depth+1)),new THREE.LineBasicMaterial({color:'#eab37c',transparent:true,opacity:.7}));edges.position.y=b.floors*b.floor_height/2;structure.add(edges);}
    }
    for(const f of props.subject.features.filter(feature=>!feature.building_id)){const st=props.state[f.id]||f.state,resource=proceduralSiteResource(f,st);if(resource)scene.add(resource);
      if(resource&&['HYDRANT','ASSEMBLY','HOSPITAL'].includes(f.kind)){const tag=label(f.id+(st.water==='UNAVAILABLE'?' · 용수 사용 불가':''),'#b7d4f1',9);tag.position.set(f.x,3,f.z);scene.add(tag);}
      if(f.kind==='ROAD'&&st.closed){const tag=label('진입 통제','#ffbb77',13);tag.position.set(f.x,3.4,f.z);scene.add(tag);}
    }
    if(props.subject.target_mode==='VIRTUAL')for(const [x,z] of [[-85,-55],[-75,55],[85,55],[98,-57],[-98,25],[80,-58],[-90,-38]]){box(.6,3,.6,'#6c5d4c',[x,1.5,z]);mesh(new THREE.IcosahedronGeometry(3,1),mat('#405e4d'),[x,5,z]);}
    const north=label('N ↑','#9db4c1',10);north.position.set(-85,1,-65);scene.add(north);
    const ray=new THREE.Raycaster();const pointer=new THREE.Vector2();let down=[0,0];const onDown=(e:PointerEvent)=>{down=[e.clientX,e.clientY];};const onUp=(e:PointerEvent)=>{if(Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;const r=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(scene.children,true).find(h=>h.object.userData.buildingId||h.object.userData.featureId);if(hit){onSelect.current(hit.object.userData.featureId||hit.object.userData.buildingId);setObjectInfo(String(hit.object.userData.assetNode||''));}};renderer.domElement.addEventListener('pointerdown',onDown);renderer.domElement.addEventListener('pointerup',onUp);
    const resize=()=>{const w=node.clientWidth,h=Math.max(180,node.clientHeight);renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};const observer=new ResizeObserver(resize);observer.observe(node);resize();
    let frame=0,count=0,start=performance.now(),sampled=false,low=0;let quality='L1';
    const contextLost=(e:Event)=>{e.preventDefault();setFailed(true);};renderer.domElement.addEventListener('webglcontextlost',contextLost);
    const render=()=>{frame=requestAnimationFrame(render);controls.update();renderer.render(scene,camera);count++;const now=performance.now();if(now-start>=2000){const fps=count*1000/(now-start);onPerf.current?.(Math.round(fps),renderer.info.render.triangles,quality);if(fps<24&&!sampled){renderer.setPixelRatio(1);renderer.shadowMap.enabled=false;quality='L0';sampled=true;}else if(fps<18&&sampled){low++;if(low>=3)setFailed(true);}count=0;start=now;}};render();
    return ()=>{savedView.current={position:camera.position.clone(),target:controls.target.clone(),view:props.cameraView,reset:props.resetKey,assets:assetSignature};assetController.abort();cancelAnimationFrame(frame);observer.disconnect();controls.dispose();renderer.domElement.removeEventListener('pointerdown',onDown);renderer.domElement.removeEventListener('pointerup',onUp);renderer.domElement.removeEventListener('webglcontextlost',contextLost);scene.traverse(o=>{if(o instanceof THREE.LineSegments){o.geometry.dispose();const materials=Array.isArray(o.material)?o.material:[o.material];materials.forEach(m=>m.dispose());}if(o instanceof THREE.Sprite)o.material.dispose();});disposeAsset(scene);textures.forEach(t=>t.dispose());renderer.dispose();renderer.domElement.remove();};
  },[props.subject,props.state,props.selected,props.hiddenFloor,props.cutaway,props.exploded,props.cameraView,props.resetKey,props.assetBase,failed]);
  const fallbackExtent=Math.max(110,siteRadius({...props.subject,buildings:props.subject.buildings.map(b=>assetDisplayBuilding(props.subject,b))},props.state)/.7,...props.subject.buildings.map(b=>Math.max(Math.abs(b.x)+b.width,Math.abs(b.z)+b.depth)));
  const summaries=sceneStateSummary(props.subject,props.state);
  if(failed)return <div className="scene-fallback" role="region" aria-label="2D 상황판 상태 목록" tabIndex={0} onKeyDown={event=>{if(event.target!==event.currentTarget||!["Home","End"].includes(event.key))return;event.preventDefault();const node=event.currentTarget;node.scrollTop=event.key==="End"?node.scrollHeight:0;(event.key==="End"?node.querySelector("li:last-child"):node.firstElementChild)?.scrollIntoView({block:"nearest",behavior:"instant"});}}><strong>2D 평면도 · 동일 사건 상태 유지</strong><small>{props.subject.name}</small><p>3D 미지원·성능 저하·장면 예산 초과로 도식으로 전환했습니다. 상태 수치는 훈련용 연출입니다. 상태 목록은 스크롤해 확인하세요.</p><svg viewBox={`${-fallbackExtent} ${-fallbackExtent*.7} ${fallbackExtent*2} ${fallbackExtent*1.4}`} role="img" aria-label="가상 건물 평면도">{props.subject.buildings.map(b=>assetDisplayBuilding(props.subject,b)).map(b=><g key={b.id} onClick={()=>props.onSelect(b.id)}><g transform={`translate(${b.x} ${b.z}) rotate(${-b.rotation-props.subject.north_rotation})`}>{b.footprint.length>=3?<polygon points={b.footprint.map(point=>point.join(',')).join(' ')} fill={b.color} stroke={b.id===props.selected?'#f5b476':'#e2edf3'}/>:<rect x={-b.width/2} y={-b.depth/2} width={b.width} height={b.depth} fill={b.color} stroke={b.id===props.selected?'#f5b476':'#e2edf3'} strokeWidth="1"/>}</g><text x={b.x} y={b.z} textAnchor="middle" fontSize={Math.max(5,fallbackExtent/22)} fill="#10202c">{b.id} {b.floors}F</text></g>)}</svg><ul className="scene-state-list" aria-label="2D 상황 정보">{sceneStateSummary(props.subject,props.state).map(item=><li key={item.id}><strong>{item.name} <small>{item.id}</small></strong><span>{item.details}</span></li>)}</ul></div>;
  return <div ref={host} className="three-host"><details className="scene-state-summary"><summary>사건 상태 요약 · {summaries.length}개</summary><p>같은 사건 버전의 훈련 설정·연출입니다.</p><ul className="scene-state-list">{summaries.map(item=><li key={item.id}><strong>{item.name} <small>{item.id}</small></strong><span>{item.details}</span></li>)}</ul></details>{Boolean(Object.keys(assetStates).length)&&<div className="scene-asset-status" role="status">{Object.entries(assetStates).map(([id,text])=><span data-asset-binding={id} key={id}>{text}</span>)}</div>}{objectInfo&&<div className="scene-object-info">{objectInfo}</div>}</div>;
}
