import {useRef} from 'react';
import {entityPosition,type SceneState,type Side} from './types';
export function SiteMap({state,select,onPlace}:{state:SceneState;select?:string;onPlace?:(x:number,z:number)=>void}){
 const mapRef=useRef<SVGSVGElement>(null);
 return <svg ref={mapRef} className={`site-map ${onPlace?'editable-map':''}`} viewBox="-125 -115 250 225" role={onPlace?'application':'img'} aria-label={onPlace?'배치 지도. 클릭하면 선택한 자원을 배치합니다.':'현장 배치 지도. 위에서 본 시계방향 A B C D.'} onClick={event=>{if(!onPlace||!mapRef.current)return;const matrix=mapRef.current.getScreenCTM();if(!matrix)return;const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());onPlace(Math.round(point.x),Math.round(point.y));}}>
  <rect x="-125" y="-115" width="250" height="225" fill="#e9eee8"/><path d="M-125 66H125M-94-115V115M95-115V115M-125-77H125" stroke="#c4ccc9" strokeWidth="14"/>
  <g transform={`translate(-110,-98) rotate(${state.site.front_bearing-180})`}><path d="M0 7V-7M-2-3L0-7L2-3" stroke="#748a97" strokeWidth="1" fill="none"/><text x="0" y="-11" textAnchor="middle" fontSize="5" fill="#647d8c">N</text></g>
  {state.buildings.map(b=><g key={b.id}><rect x={b.x-b.width/2} y={b.z-b.depth/2} width={b.width} height={b.depth} fill="#c2cbcb" stroke="#859696" strokeWidth=".8"/><text x={b.x} y={b.z} textAnchor="middle" className="map-building">{b.id}</text></g>)}
  {state.entities.filter(e=>e.visible).map(e=>{const [x,,z]=entityPosition(e,state.buildings);return <g key={e.id}><circle cx={x} cy={z} r={e.kind==='fire'?3:2.3} fill={e.kind==='fire'?'#e7753e':e.kind==='hydrant'?'#159e91':e.kind==='victim'?'#b36c96':'#566f8d'} stroke={select===e.id?'#ed6c3b':'white'} strokeWidth={select===e.id?2:1}/></g>;})}
  {(['A','B','C','D']as Side[]).map((s,i)=><text key={s} x={[0,-115,0,115][i]} y={[98,0,-101,0][i]} textAnchor="middle" className={`map-side ${s==='A'?'front':''}`}>{s}</text>)}
 </svg>;
}

