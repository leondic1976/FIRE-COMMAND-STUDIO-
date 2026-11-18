import {lazy,Suspense} from 'react';
import Scene,{type Props} from './Scene';
const VWorldScene=lazy(()=>import('./VWorldScene'));
export default function FieldScene(props:Props){
 return props.state.site.map_provider==='vworld'?<Suspense fallback={<div className="stage-loading">브이월드 화면 준비 중</div>}><VWorldScene {...props}/></Suspense>:<Scene {...props}/>;
}
