import {lazy,Suspense} from 'react';
import type {SceneProps} from './Scene';
const LoadedScene=lazy(()=>import('./Scene').then(module=>({default:module.Scene})));
export function Scene(props:SceneProps){return <Suspense fallback={<div className="scene-fallback"><strong>가상 3D 장면 준비 중</strong><p>훈련용 모델과 주변 배치를 불러오고 있습니다.</p></div>}><LoadedScene {...props}/></Suspense>;}
