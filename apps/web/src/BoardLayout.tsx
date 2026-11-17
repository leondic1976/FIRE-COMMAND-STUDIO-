import {useState,type CSSProperties,type ReactNode} from 'react';
import {RotateCcw} from 'lucide-react';
import './board-layout.css';

export function BoardLayout({children}:{children:ReactNode}){
 const [width,setWidth]=useState(66),[height,setHeight]=useState(550),[pinned,setPinned]=useState(false);
 const style={'--board-width':width+'fr','--board-side-width':(100-width)+'fr','--board-height':height+'px'} as CSSProperties;
 return <><div className="board-layout-toolbar" role="group" aria-label="상황판 화면 배치"><label className="layout-width">3D 영역 너비 <output>{width}%</output><input aria-label="3D 영역 너비" type="range" min={50} max={78} value={width} onChange={e=>setWidth(Number(e.target.value))}/></label><label>3D 화면 높이 <output>{height}px</output><input aria-label="3D 화면 높이" type="range" min={320} max={900} step={10} value={height} onChange={e=>setHeight(Number(e.target.value))}/></label><label className="layout-pin"><input type="checkbox" checked={pinned} onChange={e=>setPinned(e.target.checked)}/>상황판 안에서 메시지 위치 고정</label><button className="button small" onClick={()=>{setWidth(66);setHeight(550);setPinned(false);}}><RotateCcw size={13}/>화면 배치 원위치</button></div><div data-layout="adjustable" className={`board-grid board-configurable ${pinned?'messages-pinned':''}`} style={style}>{children}</div></>;
}
