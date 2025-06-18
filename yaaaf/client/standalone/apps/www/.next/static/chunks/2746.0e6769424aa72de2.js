"use strict";(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[2746,6719,86],{77914:(e,t,n)=>{n.r(t),n.d(t,{default:()=>i});var r=n(57437),l=n(2265),a=n(79951),s=n(34929);function i(){let[e,t]=(0,l.useState)(""),[n,i]=(0,l.useState)(!1),o=(0,l.useRef)(),d=()=>{o.current&&window.clearTimeout(o.current)},u=(e,t)=>{d();let n=window.setTimeout(e,t);o.current=n};return(0,r.jsx)(a.ChatForm,{className:"w-full max-w-[500px]",isPending:!1,handleSubmit:e=>{var n;null==e||null===(n=e.preventDefault)||void 0===n||n.call(e),t(""),i(!0),u(()=>{i(!1)},2e3)},children:(0,r.jsx)(s.MessageInput,{value:e,onChange:e=>{t(e.target.value)},stop:()=>{i(!1),d()},isGenerating:n})})}},45811:(e,t,n)=>{n.d(t,{M:()=>k});var r=n(57437),l=n(2265),a=n(46673),s=n(43768),i=n(29149),o=n(85853);class d extends l.Component{getSnapshotBeforeUpdate(e){let t=this.props.childRef.current;if(t&&e.isPresent&&!this.props.isPresent){let e=this.props.sizeRef.current;e.height=t.offsetHeight||0,e.width=t.offsetWidth||0,e.top=t.offsetTop,e.left=t.offsetLeft}return null}componentDidUpdate(){}render(){return this.props.children}}function u(e){let{children:t,isPresent:n}=e,a=(0,l.useId)(),s=(0,l.useRef)(null),i=(0,l.useRef)({width:0,height:0,top:0,left:0}),{nonce:u}=(0,l.useContext)(o._);return(0,l.useInsertionEffect)(()=>{let{width:e,height:t,top:r,left:l}=i.current;if(n||!s.current||!e||!t)return;s.current.dataset.motionPopId=a;let o=document.createElement("style");return u&&(o.nonce=u),document.head.appendChild(o),o.sheet&&o.sheet.insertRule('\n          [data-motion-pop-id="'.concat(a,'"] {\n            position: absolute !important;\n            width: ').concat(e,"px !important;\n            height: ").concat(t,"px !important;\n            top: ").concat(r,"px !important;\n            left: ").concat(l,"px !important;\n          }\n        ")),()=>{document.head.removeChild(o)}},[n]),(0,r.jsx)(d,{isPresent:n,childRef:s,sizeRef:i,children:l.cloneElement(t,{ref:s})})}let h=e=>{let{children:t,initial:n,isPresent:a,onExitComplete:o,custom:d,presenceAffectsLayout:h,mode:p}=e,f=(0,s.h)(c),m=(0,l.useId)(),y=(0,l.useCallback)(e=>{for(let t of(f.set(e,!0),f.values()))if(!t)return;o&&o()},[f,o]),k=(0,l.useMemo)(()=>({id:m,initial:n,isPresent:a,custom:d,onExitComplete:y,register:e=>(f.set(e,!1),()=>f.delete(e))}),h?[Math.random(),y]:[a,y]);return(0,l.useMemo)(()=>{f.forEach((e,t)=>f.set(t,!1))},[a]),l.useEffect(()=>{a||f.size||!o||o()},[a]),"popLayout"===p&&(t=(0,r.jsx)(u,{isPresent:a,children:t})),(0,r.jsx)(i.O.Provider,{value:k,children:t})};function c(){return new Map}var p=n(31463);let f=e=>e.key||"";function m(e){let t=[];return l.Children.forEach(e,e=>{(0,l.isValidElement)(e)&&t.push(e)}),t}var y=n(27009);let k=e=>{let{children:t,custom:n,initial:i=!0,onExitComplete:o,presenceAffectsLayout:d=!0,mode:u="sync",propagate:c=!1}=e,[k,Z]=(0,p.oO)(c),v=(0,l.useMemo)(()=>m(t),[t]),x=c&&!k?[]:v.map(f),g=(0,l.useRef)(!0),w=(0,l.useRef)(v),M=(0,s.h)(()=>new Map),[C,q]=(0,l.useState)(v),[E,R]=(0,l.useState)(v);(0,y.L)(()=>{g.current=!1,w.current=v;for(let e=0;e<E.length;e++){let t=f(E[e]);x.includes(t)?M.delete(t):!0!==M.get(t)&&M.set(t,!1)}},[E,x.length,x.join("-")]);let b=[];if(v!==C){let e=[...v];for(let t=0;t<E.length;t++){let n=E[t],r=f(n);x.includes(r)||(e.splice(t,0,n),b.push(n))}"wait"===u&&b.length&&(e=b),R(m(e)),q(v);return}let{forceRender:j}=(0,l.useContext)(a.p);return(0,r.jsx)(r.Fragment,{children:E.map(e=>{let t=f(e),l=(!c||!!k)&&(v===E||x.includes(t));return(0,r.jsx)(h,{isPresent:l,initial:(!g.current||!!i)&&void 0,custom:l?void 0:n,presenceAffectsLayout:d,mode:u,onExitComplete:l?void 0:()=>{if(!M.has(t))return;M.set(t,!0);let e=!0;M.forEach(t=>{t||(e=!1)}),e&&(null==j||j(),R(w.current),c&&(null==Z||Z()),o&&o())},children:e},t)})})}},16343:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("ArrowDown",[["path",{d:"M12 5v14",key:"s699le"}],["path",{d:"m19 12-7 7-7-7",key:"1idqje"}]])},44639:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("ArrowUp",[["path",{d:"m5 12 7-7 7 7",key:"hav0vg"}],["path",{d:"M12 19V5",key:"x0mq9r"}]])},49067:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("Ban",[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"m4.9 4.9 14.2 14.2",key:"1m5liu"}]])},78169:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("ChevronRight",[["path",{d:"m9 18 6-6-6-6",key:"mthhwq"}]])},76660:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("CodeXml",[["path",{d:"m18 16 4-4-4-4",key:"1inbqp"}],["path",{d:"m6 8-4 4 4 4",key:"15zrgr"}],["path",{d:"m14.5 4-5 16",key:"e7oirm"}]])},47774:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("Dot",[["circle",{cx:"12.1",cy:"12.1",r:"1",key:"18d7e5"}]])},27069:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("File",[["path",{d:"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z",key:"1rqfz7"}],["path",{d:"M14 2v4a2 2 0 0 0 2 2h4",key:"tnqrlb"}]])},85712:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("LoaderCircle",[["path",{d:"M21 12a9 9 0 1 1-6.219-8.56",key:"13zald"}]])},8423:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("Square",[["rect",{width:"18",height:"18",x:"3",y:"3",rx:"2",key:"afitv7"}]])},99118:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("Terminal",[["polyline",{points:"4 17 10 11 4 5",key:"akl6gq"}],["line",{x1:"12",x2:"20",y1:"19",y2:"19",key:"q2wloq"}]])},36871:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("ThumbsDown",[["path",{d:"M17 14V2",key:"8ymqnk"}],["path",{d:"M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z",key:"s6e0r"}]])},28556:(e,t,n)=>{n.d(t,{Z:()=>r});/**
 * @license lucide-react v0.359.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */let r=(0,n(85666).Z)("ThumbsUp",[["path",{d:"M7 10v12",key:"1qc93n"}],["path",{d:"M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z",key:"y3tblf"}]])}}]);