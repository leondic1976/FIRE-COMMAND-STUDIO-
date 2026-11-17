import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {disposeAsset,loadAssetModel} from './asset-runtime';

export default function AssetPreview({url,sha256,selectedNode,onNodeSelect}:{url:string;sha256:string;selectedNode:number|null;onNodeSelect:(index:number)=>void}){
 const host=useRef<HTMLDivElement>(null),[error,setError]=useState(''),[ready,setReady]=useState(false);
 const pick=useRef(onNodeSelect);pick.current=onNodeSelect;
 const selected=useRef(selectedNode);selected.current=selectedNode;
 useEffect(()=>{const node=host.current;if(!node)return;setReady(false);setError('');const controller=new AbortController();let renderer:THREE.WebGLRenderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true});}catch{setError('3D를 표시할 수 없습니다. 객체 목록·수치 또는 승인된 오프라인 도구로 확인하세요.');return;}
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setClearColor('#172331');renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.domElement.setAttribute('aria-label','검토 대상 GLB. 드래그로 회전, 객체를 클릭해 이름과 층 연결을 확인합니다.');renderer.domElement.setAttribute('role','img');node.appendChild(renderer.domElement);
  const scene=new THREE.Scene();scene.add(new THREE.HemisphereLight('#ffffff','#52606b',3));const light=new THREE.DirectionalLight('#ffe8cf',3);light.position.set(10,20,10);scene.add(light);
  const camera=new THREE.PerspectiveCamera(40,1,.01,10000),controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
  let object:THREE.Object3D|undefined,box:THREE.BoxHelper|undefined,raf=0;const nodes=new Map<number,THREE.Object3D>();
  const observer=new ResizeObserver(()=>{if(!node.clientWidth)return;renderer.setSize(node.clientWidth,320,false);camera.aspect=node.clientWidth/320;camera.updateProjectionMatrix();});observer.observe(node);
  const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();let down=[0,0];
  const onDown=(event:PointerEvent)=>{down=[event.clientX,event.clientY];};
  const onUp=(event:PointerEvent)=>{if(Math.hypot(event.clientX-down[0],event.clientY-down[1])>5||!object)return;const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObject(object,true)[0];if(!hit)return;let target:THREE.Object3D|null=hit.object;while(target){const entry=Array.from(nodes).find(([,value])=>value===target);if(entry){pick.current(entry[0]);break;}target=target.parent;}};
  renderer.domElement.addEventListener('pointerdown',onDown);renderer.domElement.addEventListener('pointerup',onUp);
  void loadAssetModel(url,sha256,controller.signal).then(result=>{object=result.root;result.nodes.forEach((value,key)=>nodes.set(key,value));scene.add(object);const bounds=new THREE.Box3().setFromObject(object),center=bounds.getCenter(new THREE.Vector3()),radius=bounds.getSize(new THREE.Vector3()).length();controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(radius*.9,radius*.7,radius));camera.far=Math.max(100,radius*10);camera.updateProjectionMatrix();controls.update();last=Number.NaN;setReady(true);}).catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:'모델을 표시할 수 없습니다.');});
  let last:number|null=null;function frame(){raf=requestAnimationFrame(frame);controls.update();if(last!==selected.current){if(box){scene.remove(box);box.geometry.dispose();(box.material as THREE.Material).dispose();box=undefined;}const target=selected.current===null?undefined:nodes.get(selected.current);if(target){box=new THREE.BoxHelper(target,'#f4b779');scene.add(box);}last=selected.current;}renderer.render(scene,camera);}frame();
  return()=>{controller.abort();cancelAnimationFrame(raf);observer.disconnect();renderer.domElement.removeEventListener('pointerdown',onDown);renderer.domElement.removeEventListener('pointerup',onUp);controls.dispose();if(box){box.geometry.dispose();(box.material as THREE.Material).dispose();}if(object)disposeAsset(object);renderer.dispose();renderer.domElement.remove();};
 },[url,sha256]);
 return <div className="asset-preview"><div ref={host} className="asset-preview-canvas" data-asset-ready={ready}/>{error?<p role="alert">{error}</p>:!ready&&<p>검사된 모델 로딩 중…</p>}<p className="small muted">검사된 파일의 비공개 미리보기 · 이용권/공개범위 승인은 별도 · 키보드로는 아래 객체 목록을 사용하세요.</p></div>;
}
