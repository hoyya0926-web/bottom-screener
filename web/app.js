// 바닥신호 스크리너 페이지 — results.json(목록·분석)과 data/*.json(차트)을 읽어 그립니다.
const LC = window.LightweightCharts;
const MKT = {US:"미국", KR:"국내", CR:"코인"};
const SIG = [
  {k:"w20", t:"주봉 RSI ≤ 20", imp:true},
  {k:"div3", t:"다이버전스 주·일·4H"},
  {k:"div2", t:"다이버전스 일·4H"},
  {k:"fvg", t:"바닥 거래량 + FVG"},
  {k:"box", t:"고점 후 4주+ 횡보"},
];
const SIGT = Object.fromEntries(SIG.map(s => [s.k, s.t]));
const TFS = [["1m","1분"],["15m","15분"],["1h","1시간"],["4h","4시간"],["1d","일봉"],["1w","주봉"],["1M","월봉"]];
const TFN = Object.fromEntries(TFS);
const INTRA = new Set(["1m","15m","1h","4h"]);
const PY_TF = new Set(["4h","1d","1w"]);           // 이 셋은 서버(파이썬) 판정을 그대로 표시
const LIVE_BAR = {"1m":"1m","15m":"15m","1h":"1H"}; // 코인 실시간 갱신 대상
const DAYS = "일월화수목금토";
let DATA = [], META = null, LIVE_OK = true;

// ---------- 포맷 ----------
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function fpx(T,p){if(p==null)return "—";if(T.m==="KR")return Math.round(p).toLocaleString("ko-KR")+"원";if(T.m==="US")return "$"+p.toFixed(2);if(p>=1000)return "$"+Math.round(p).toLocaleString("en-US");if(p>=1)return "$"+p.toFixed(3);return "$"+p.toPrecision(3)}
function prec(T,p){if(T.m==="KR")return 0;if(T.m==="US")return 2;return p>=1000?1:p>=10?2:p>=1?3:p>=.01?5:8}
function fcap(T){if(T.cap==null)return T.m==="CR"?"거래대금 상위":"—";if(T.m==="KR")return T.cap+"조원";return "$"+(T.cap>=1000?(T.cap/1000).toFixed(1)+"T":T.cap+"B")}
function rsiState(v){if(v==null)return "—";if(v<=20)return "극단적 과매도";if(v<30)return "과매도";if(v<45)return "약세";if(v<=55)return "중립";if(v<70)return "강세";return "과매수"}
function links(T){
  if(T.m==="KR")return [["TradingView","https://www.tradingview.com/chart/?symbol=KRX:"+T.s],["네이버 증권","https://m.stock.naver.com/domestic/stock/"+T.s+"/total"]];
  if(T.m==="US"){const s=T.s.replace("-",".");const suf={NYSE:".N",AMEX:".A"}[T.venue]||".O";return [["TradingView","https://www.tradingview.com/chart/?symbol="+(T.venue?T.venue+":":"")+s],["네이버 증권","https://m.stock.naver.com/worldstock/stock/"+s+suf+"/total"]]}
  return [["TradingView","https://www.tradingview.com/chart/?symbol=OKX:"+T.s+"USDT"],["BingX","https://bingx.com/en/spot/"+T.s+"USDT/"],["OKX","https://www.okx.com/trade-spot/"+T.s.toLowerCase()+"-usdt"]];
}
function capPass(T,rule){if(rule==="all")return true;if(rule==="mid")return T.capOk;if(T.cap==null)return T.m==="CR"?T.pop>=75:true;return T.cap>=(T.m==="KR"?20:200)}

// ---------- 지표 (서버와 같은 규칙) ----------
function rsiCalc(c,p=14){const r=new Array(c.length).fill(null);if(c.length<=p)return r;let g=0,l=0;for(let i=1;i<=p;i++){const d=c[i]-c[i-1];if(d>0)g+=d;else l-=d}g/=p;l/=p;r[p]=l===0?100:100-100/(1+g/l);for(let i=p+1;i<c.length;i++){const d=c[i]-c[i-1];g=(g*(p-1)+Math.max(d,0))/p;l=(l*(p-1)+Math.max(-d,0))/p;r[i]=l===0?100:100-100/(1+g/l)}return r}
function pivL(low,L,R){const o=[];for(let i=L;i<low.length-R;i++){let ok=true;for(let k=1;k<=L&&ok;k++)if(low[i-k]<=low[i])ok=false;for(let k=1;k<=R&&ok;k++)if(low[i+k]<low[i])ok=false;if(ok)o.push(i)}return o}
function rm(r,i){let m=Infinity;for(let k=i-1;k<=i+1;k++)if(r[k]!=null&&r[k]<m)m=r[k];return m}
function bullDiv(low,r,c){const n=low.length;const pv=pivL(low,3,c.R).filter(i=>r[i]!=null);if(!pv.length)return null;const p2=pv[pv.length-1];if(n-1-p2>c.fresh)return null;for(let i=p2+1;i<n;i++)if(low[i]<low[p2])return null;let best=null;for(let j=pv.length-2;j>=0;j--){const p1=pv[j],g=p2-p1;if(g<c.minGap)continue;if(g>c.maxGap)break;const a1=rm(r,p1),a2=rm(r,p2);if(low[p2]<low[p1]&&a2>a1+2&&a1<45){const s=a2-a1;if(!best||s>best.s)best={p1,p2,s,r1:a1,r2:a2}}}return best}
const DIVCFG = {intra:{R:2,fresh:10,minGap:4,maxGap:40}, M:{R:1,fresh:3,minGap:4,maxGap:40}};

// ---------- 분석 글 ----------
function chipsHTML(T){
  const c=[];
  if(T.sig.w20)c.push(`<span class="chip imp">중요 · 주봉 RSI ${T.wrsi.v}</span>`);
  if(T.divTf.length)c.push(`<span class="chip sig">RSI 다이버전스 <span class="tfb"><i class="${T.div["1w"]?"on":""}">주</i><i class="${T.div["1d"]?"on":""}">일</i><i class="${T.div["4h"]?"on":""}">4H</i></span></span>`);
  if(T.fvg)c.push(`<span class="chip sig">거래량 ${T.fvg.vx}× + FVG</span>`);
  if(T.box)c.push(`<span class="chip sig">횡보 ${T.box.wk}주</span>`);
  return c.join("");
}
function rsiStrip(an){
  return `<div class="rsis">${an.rsi.map(x=>{const cls=x.v==null?"":x.v<30?" os":x.v>=70?" ob":"";return `<div class="rc${cls}"><span>${x.name}</span><b>${x.v==null?"—":x.v.toFixed(0)}</b><i>${x.st}</i></div>`}).join("")}</div>`;
}
function detailHTML(T){
  const an=T.an;
  const lv=(arr)=>arr.length?arr.map(z=>`<li><span>${esc(z.l)}</span><b>${fpx(T,z.p)}</b></li>`).join(""):`<li><span class="mute">해당 없음</span></li>`;
  return `<ul class="reasons">${an.signals.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
    <div class="lv"><div class="sup"><span class="label">아래 지지 가격</span><ul>${lv(an.support)}</ul></div><div class="res"><span class="label">위 저항 가격</span><ul>${lv(an.resist)}</ul></div></div>
    ${an.watch.length?`<div class="watch"><span class="label">체크 포인트</span><ul>${an.watch.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div>`:""}`;
}
function defaultTf(T){return T.sig.w20?"1w":T.divTf.includes("1d")||T.fvg||T.box?"1d":T.divTf.includes("4h")?"4h":"1d"}
function rowHTML(T,rank,isTop){
  const chgC=T.chg>=0?"var(--up)":"var(--down)",tf=defaultTf(T);
  return `<article class="row${isTop?" top5":""}${T.sig.w20?" isimp":""}">
  <div class="rh">
    <div class="idline"><span class="rank">${rank}</span><span class="nm">${esc(T.n)}</span><span class="sym">${esc(T.s)}</span><span class="mk">${MKT[T.m]}${T.venue?" · "+esc(T.venue):""}</span></div>
    <div class="stats"><span class="score"><span class="v">${T.score}</span><span>점</span></span>
      <span>종가 <b class="num">${fpx(T,T.last)}</b> <span class="num" style="color:${chgC}">${T.chg>=0?"+":""}${T.chg.toFixed(2)}%</span></span>
      <span>시총 <b class="num">${fcap(T)}</b></span><span>인기 <b class="num">${T.pop}</b></span></div>
    <div class="chips">${chipsHTML(T)}</div>
  </div>
  <div class="chart" data-id="${T.idx}" data-tf="${tf}">
    <div class="ctb"><div class="seg tfs" role="group" aria-label="타임프레임">${TFS.map(([k,n])=>`<button type="button" data-tf="${k}" aria-pressed="${k===tf}">${n}</button>`).join("")}</div>
      <button type="button" class="fit" title="최근 구간으로 맞춤">맞춤</button></div>
    <div class="cv"><div class="ph">차트 준비 중</div></div>
    <div class="cst">&nbsp;</div>
  </div>
  <div class="ra">
    <div class="an">
      <p class="ahead">${esc(T.an.head)}</p>
      <p class="asum">${esc(T.an.summary)}</p>
      ${rsiStrip(T.an)}
      ${isTop?detailHTML(T):`<details class="more"><summary>신호 설명 · 지지/저항 · 체크 포인트</summary><div>${detailHTML(T)}</div></details>`}
    </div>
    <div class="links">${links(T).map(([l,u])=>`<a href="${u}" target="_blank" rel="noopener">${l} ↗</a>`).join("")}</div>
  </div>
</article>`;
}

// ---------- 차트 ----------
function cssv(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()}
function colors(){return {bg:cssv("--panel"),ink:cssv("--ink"),mute:cssv("--mute"),line:cssv("--line"),grid:cssv("--grid"),acc:cssv("--accent"),up:cssv("--up"),dn:cssv("--down"),upv:cssv("--upv"),dnv:cssv("--downv")}}
const FILES = new Map();
function getFile(T){
  if(!FILES.has(T.file)){
    FILES.set(T.file, fetch(T.file).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}).then(j=>{
      const o={};for(const tf in j){const seen=new Set(),arr=[];for(const a of j[tf]){if(seen.has(a[0]))continue;seen.add(a[0]);arr.push({time:a[0],open:a[1],high:a[2],low:a[3],close:a[4],vol:a[5]})}arr.sort((a,b)=>a.time-b.time);o[tf]=arr}return o}));
  }
  return FILES.get(T.file);
}
async function liveOKX(sym,tf){
  if(!LIVE_OK||!LIVE_BAR[tf])return null;
  const ac=new AbortController(),to=setTimeout(()=>ac.abort(),6000);
  try{
    const r=await fetch(`https://www.okx.com/api/v5/market/candles?instId=${encodeURIComponent(sym)}-USDT&bar=${LIVE_BAR[tf]}&limit=300`,{signal:ac.signal});
    const j=await r.json();if(j.code!=="0"||!j.data||!j.data.length)return null;
    return j.data.map(x=>({time:Math.floor(+x[0]/1000)+32400,open:+x[1],high:+x[2],low:+x[3],close:+x[4],vol:+x[5]})).sort((a,b)=>a.time-b.time);
  }catch(e){LIVE_OK=false;return null}finally{clearTimeout(to)}
}
function two(n){return String(n).padStart(2,"0")}
function tsFmt(t,tf){const d=new Date(t*1000);const md=`${d.getUTCMonth()+1}/${d.getUTCDate()}`;
  if(INTRA.has(tf))return `${d.getUTCFullYear()%100}/${md} ${two(d.getUTCHours())}:${two(d.getUTCMinutes())}`;
  if(tf==="1M")return `${d.getUTCFullYear()}.${two(d.getUTCMonth()+1)}`;
  return `${d.getUTCFullYear()}/${md}(${DAYS[d.getUTCDay()]})`}
function tickFmt(t,type){const d=new Date(t*1000);
  if(type===0)return String(d.getUTCFullYear());if(type===1)return `${d.getUTCMonth()+1}월`;if(type===2)return `${d.getUTCMonth()+1}/${d.getUTCDate()}`;return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}`}
function themeOpts(C){return {layout:{background:{type:"solid",color:C.bg},textColor:C.mute,fontFamily:'"IBM Plex Mono", ui-monospace, monospace',fontSize:11,panes:{separatorColor:C.line,separatorHoverColor:C.line,enableResize:false}},
  grid:{vertLines:{color:C.grid},horzLines:{color:C.grid}},rightPriceScale:{borderColor:C.line},timeScale:{borderColor:C.line}}}
function mapIdx(bars,t,tf){
  if(t==null||!bars.length||t<bars[0].time-86400*31)return -1;
  let lo=0,hi=bars.length-1,ans=-1;while(lo<=hi){const m=(lo+hi)>>1;if(bars[m].time<=t){ans=m;lo=m+1}else hi=m-1}
  if(INTRA.has(tf)){const j=ans+1;if((ans<0||bars[ans].time<t)&&j<bars.length&&bars[j].time<t+86400)return j;if(ans>=0&&bars[ans].time===t)return ans;return -1}
  return ans;
}
const CHARTS = new Set();
class Chart{
  constructor(box,T){
    this.box=box;this.T=T;this.el=box.querySelector(".cv");this.st=box.querySelector(".cst");this.tf=box.dataset.tf;this.timer=null;this.visible=true;this.extra=[];this.plines=[];
    const C=colors();this.el.innerHTML="";
    this.c=LC.createChart(this.el,{autoSize:true,...themeOpts(C),
      timeScale:{borderColor:C.line,rightOffset:6,timeVisible:true,secondsVisible:false,tickMarkFormatter:tickFmt},
      localization:{locale:"ko-KR",timeFormatter:t=>tsFmt(t,this.tf)},
      crosshair:{mode:LC.CrosshairMode.Normal},
      handleScroll:{mouseWheel:false,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},
      handleScale:{mouseWheel:false,pinch:true,axisPressedMouseMove:{time:true,price:false},axisDoubleClickReset:true}});
    const pr=prec(T,T.last),nf=new Intl.NumberFormat(T.m==="KR"?"ko-KR":"en-US",{minimumFractionDigits:pr,maximumFractionDigits:pr});
    const pf={type:"custom",minMove:Math.pow(10,-pr),formatter:p=>nf.format(p)};
    this.candle=this.c.addSeries(LC.CandlestickSeries,{upColor:C.up,downColor:C.dn,borderUpColor:C.up,borderDownColor:C.dn,wickUpColor:C.up,wickDownColor:C.dn,priceFormat:pf});
    this.candle.priceScale().applyOptions({scaleMargins:{top:.06,bottom:.2}});
    this.vol=this.c.addSeries(LC.HistogramSeries,{priceScaleId:"vol",priceFormat:{type:"volume"},lastValueVisible:false,priceLineVisible:false});
    this.c.priceScale("vol").applyOptions({scaleMargins:{top:.82,bottom:0}});
    this.rsi=this.c.addSeries(LC.LineSeries,{color:C.ink,lineWidth:1.5,priceLineVisible:false,lastValueVisible:true,crosshairMarkerRadius:3,
      priceFormat:{type:"price",precision:1,minMove:.1},autoscaleInfoProvider:()=>({priceRange:{minValue:0,maxValue:100}})},1);
    this.rl=[[70,C.line,2],[30,C.mute,2],[20,C.acc,0]].map(([p,c,s])=>this.rsi.createPriceLine({price:p,color:c,lineStyle:s,lineWidth:1,axisLabelVisible:false}));
    const ps=this.c.panes();if(ps[0]&&ps[0].setStretchFactor){ps[0].setStretchFactor(3);ps[1].setStretchFactor(1)}
    this.mk=LC.createSeriesMarkers(this.candle,[]);this.rmk=LC.createSeriesMarkers(this.rsi,[]);
    CHARTS.add(this);
  }
  destroy(){clearInterval(this.timer);try{this.c.remove()}catch(e){}CHARTS.delete(this)}
  async show(tf,quiet){
    this.tf=tf;clearInterval(this.timer);this.timer=null;
    if(!quiet)this.st.textContent=`${TFN[tf]} 불러오는 중…`;
    let all;try{all=await getFile(this.T)}catch(e){this.st.textContent="차트 데이터를 불러오지 못했습니다. 잠시 뒤 새로고침해 보세요.";return}
    if(this.tf!==tf)return;
    let bars=all[tf],live=false;
    if(this.T.m==="CR"&&LIVE_BAR[tf]){const lv=await liveOKX(this.T.s,tf);if(this.tf!==tf)return;if(lv){bars=lv;live=true}}
    if(!bars||bars.length<2){this.clear();this.st.textContent=`${TFN[tf]} 데이터가 없습니다.`;return}
    this.render(bars,tf,live,quiet);
    if(live)this.timer=setInterval(async()=>{if(!this.visible||this.tf!==tf||document.hidden)return;const lv=await liveOKX(this.T.s,tf);if(lv&&this.tf===tf)this.render(lv,tf,true,true)},30000);
  }
  clear(){this.candle.setData([]);this.vol.setData([]);this.rsi.setData([]);this.extra.forEach(s=>this.c.removeSeries(s));this.extra=[];this.plines.forEach(p=>this.candle.removePriceLine(p));this.plines=[];this.mk.setMarkers([]);this.rmk.setMarkers([])}
  render(bars,tf,live,keep){
    const C=colors(),T=this.T;
    const range=keep?this.c.timeScale().getVisibleLogicalRange():null;
    this.clear();
    this.c.applyOptions({timeScale:{timeVisible:INTRA.has(tf)}});
    this.candle.setData(bars.map(b=>({time:b.time,open:b.open,high:b.high,low:b.low,close:b.close})));
    this.vol.setData(bars.map(b=>({time:b.time,value:b.vol,color:b.close>=b.open?C.upv:C.dnv})));
    const r=rsiCalc(bars.map(b=>b.close));
    this.rsi.setData(bars.map((b,i)=>r[i]==null?{time:b.time}:{time:b.time,value:+r[i].toFixed(2)}));
    const mk=[],rmk=[],low=bars.map(b=>b.low);
    // 다이버전스
    let dv=null,src="";
    if(PY_TF.has(tf)){const d=T.div[tf];if(d){const i1=mapIdx(bars,d.t1,"x"),i2=mapIdx(bars,d.t2,"x");if(i1>=0&&i2>=0&&bars[i1].time===d.t1&&bars[i2].time===d.t2)dv={i1,i2,p1:d.p1,p2:d.p2,r1:d.r1,r2:d.r2};src=d?"server":""}}
    else{const d=bullDiv(low,r,tf==="1M"?DIVCFG.M:DIVCFG.intra);if(d)dv={i1:d.p1,i2:d.p2,p1:low[d.p1],p2:low[d.p2],r1:d.r1,r2:d.r2};src=d?"page":""}
    if(dv){
      const o={color:C.acc,lineWidth:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,pointMarkersVisible:true,pointMarkersRadius:3};
      const a=this.c.addSeries(LC.LineSeries,o);a.setData([{time:bars[dv.i1].time,value:dv.p1},{time:bars[dv.i2].time,value:dv.p2}]);
      const b=this.c.addSeries(LC.LineSeries,o,1);b.setData([{time:bars[dv.i1].time,value:+rm(r,dv.i1).toFixed(2)},{time:bars[dv.i2].time,value:+rm(r,dv.i2).toFixed(2)}]);
      this.extra.push(a,b);
      mk.push({time:bars[dv.i2].time,position:"belowBar",color:C.acc,shape:"arrowUp",text:"다이버전스"});
    }
    // FVG · 박스
    if(T.fvg){
      this.plines.push(this.candle.createPriceLine({price:T.fvg.hi,color:C.acc,lineStyle:2,lineWidth:1,axisLabelVisible:true,title:"FVG"}));
      this.plines.push(this.candle.createPriceLine({price:T.fvg.lo,color:C.acc,lineStyle:2,lineWidth:1,axisLabelVisible:true,title:""}));
      const i=mapIdx(bars,T.fvg.tv,tf);if(i>=0)mk.push({time:bars[i].time,position:"belowBar",color:C.acc,shape:"arrowUp",text:`거래량 ${T.fvg.vx}×`});
    }
    if(T.box){
      this.plines.push(this.candle.createPriceLine({price:T.box.hi,color:C.mute,lineStyle:1,lineWidth:1,axisLabelVisible:true,title:"박스"}));
      this.plines.push(this.candle.createPriceLine({price:T.box.lo,color:C.mute,lineStyle:1,lineWidth:1,axisLabelVisible:true,title:""}));
      const ip=mapIdx(bars,T.box.tp,tf);if(ip>=0)mk.push({time:bars[ip].time,position:"aboveBar",color:C.mute,shape:"circle",text:"고점"});
      const is=mapIdx(bars,T.box.t0,tf);if(is>=0&&!INTRA.has(tf))mk.push({time:bars[is].time,position:"aboveBar",color:C.mute,shape:"square",text:"횡보 시작"});
    }
    if(tf==="1w"&&T.sig.w20&&T.wrsi.t!=null){const i=mapIdx(bars,T.wrsi.t,tf);if(i>=0)rmk.push({time:bars[i].time,position:"belowBar",color:C.acc,shape:"circle",text:`RSI ${T.wrsi.v}`})}
    const byT=(a,b)=>a.time-b.time;
    this.mk.setMarkers(mk.sort(byT));this.rmk.setMarkers(rmk.sort(byT));
    const n=bars.length;
    if(range)this.c.timeScale().setVisibleLogicalRange(range);else this.fit(n);
    // 상태 줄
    const last=bars[n-1],prev=bars[n-2],ch=(last.close/prev.close-1)*100,rv=r[n-1];
    const dvTxt=dv?`<span class="on">상승 다이버전스 (RSI ${dv.r1.toFixed(0)}→${dv.r2.toFixed(0)})</span>`:"다이버전스 없음";
    const srcTxt=live?`<span class="on">실시간 OKX · ${tsFmt(last.time,tf)}</span>`:`마지막 봉 ${tsFmt(last.time,tf)}`;
    this.st.innerHTML=`<b>${TFN[tf]}</b> · ${fpx(T,last.close)} <span style="color:${ch>=0?"var(--up)":"var(--down)"}">${ch>=0?"+":""}${ch.toFixed(2)}%</span> · RSI <b>${rv==null?"—":rv.toFixed(1)}</b> ${rsiState(rv)} · ${dvTxt} · ${srcTxt}`;
    this.n=n;
  }
  fit(n){n=n||this.n;if(!n)return;const w=this.el.clientWidth||360;const show=Math.min(n,Math.max(40,Math.round(w/6)));this.c.timeScale().setVisibleLogicalRange({from:n-show,to:n+5})}
}
const io=new IntersectionObserver(es=>{for(const e of es){const box=e.target;let ch=box._chart;
  if(e.isIntersecting&&!ch&&LC){const T=DATA[+box.dataset.id];if(!T)continue;ch=box._chart=new Chart(box,T);ch.show(box.dataset.tf)}
  if(ch)ch.visible=e.isIntersecting}},{rootMargin:"400px 0px"});
function mountCharts(root){
  for(const ch of [...CHARTS])if(!document.body.contains(ch.el))ch.destroy();
  root.querySelectorAll(".chart").forEach(b=>{if(!LC){b.querySelector(".ph").textContent="차트 라이브러리를 불러오지 못했습니다.";return}io.observe(b)});
}

// ---------- 목록 ----------
const S={mkt:"ALL",cap:"mid",mode:"and",sort:"score",sig:new Set()};
try{const v=localStorage.getItem("scr-v2");if(v){const o=JSON.parse(v);Object.assign(S,o,{sig:new Set(o.sig||[])})}}catch(e){}
function save(){try{localStorage.setItem("scr-v2",JSON.stringify({...S,sig:[...S.sig]}))}catch(e){}}
function base(){return DATA.filter(T=>(S.mkt==="ALL"||T.m===S.mkt)&&capPass(T,S.cap))}
function rankSort(a,b){return b.score-a.score||b.pop-a.pop}
function render(){
  document.querySelectorAll("#mkt button").forEach(b=>b.setAttribute("aria-pressed",b.dataset.v===S.mkt));
  document.querySelectorAll("#mode button").forEach(b=>b.setAttribute("aria-pressed",b.dataset.v===S.mode));
  document.getElementById("cap").value=S.cap;document.getElementById("sort").value=S.sort;
  const ms=S.mkt==="ALL"?["US","KR","CR"]:[S.mkt];
  const scanned=ms.reduce((a,m)=>a+(META.scanned[m]||0),0),small=ms.reduce((a,m)=>a+(META.smallExcluded[m]||0),0);
  const B=base();
  document.getElementById("capnote").textContent=`${scanned}종목 스캔 · 신호 ${B.length}종목${S.cap==="mid"&&small?` · 소형주 ${small}종목 제외`:""}`;
  const top=document.getElementById("top5"),t5=B.slice().sort(rankSort).slice(0,5);
  top.innerHTML=t5.length?t5.map((T,i)=>rowHTML(T,i+1,true)).join(""):`<div class="empty">오늘 이 조건에서 신호가 잡힌 종목이 없습니다.</div>`;
  document.getElementById("sigs").innerHTML=SIG.map(s=>`<button type="button" class="tog" data-k="${s.k}" aria-pressed="${S.sig.has(s.k)}">${s.t}${s.imp?" · 중요":""} <span class="n">${B.filter(T=>T.sig[s.k]).length}</span></button>`).join("");
  const cm={};B.forEach(T=>{if(!T.combo.length)return;const k=T.combo.join("+");(cm[k]=cm[k]||[]).push(T)});
  const ce=Object.entries(cm).sort((a,b)=>b[0].split("+").length-a[0].split("+").length||b[1].length-a[1].length);
  document.getElementById("combos").innerHTML=ce.length?ce.map(([k,v])=>`<button type="button" class="combo" data-c="${k}"><span>${k.split("+").map(x=>SIGT[x]).join(" + ")}</span><span class="n">${v.length}</span><span class="k">${v.slice(0,3).map(T=>esc(T.n)).join(", ")}${v.length>3?" 외":""}</span></button>`).join(""):`<span class="mute">조합 없음</span>`;
  let L=B;if(S.sig.size){const ks=[...S.sig];L=B.filter(T=>S.mode==="and"?ks.every(k=>T.sig[k]):ks.some(k=>T.sig[k]))}
  const rk=new Map(B.slice().sort(rankSort).map((T,i)=>[T.idx,i+1]));
  L=L.slice().sort(S.sort==="pop"?(a,b)=>b.pop-a.pop||b.score-a.score:S.sort==="n"?(a,b)=>b.groups-a.groups||b.score-a.score:rankSort);
  document.getElementById("cnt").textContent=`${L.length}종목`;
  const list=document.getElementById("list");
  list.innerHTML=L.length?L.map(T=>rowHTML(T,rk.get(T.idx),false)).join(""):`<div class="empty">선택한 신호를 모두 가진 종목이 없습니다. 겹침 조건을 ‘하나라도’로 바꾸거나 신호를 줄여 보세요.</div>`;
  mountCharts(document);save();
}
function stamp(d){return `${d.getFullYear()}.${two(d.getMonth()+1)}.${two(d.getDate())} (${DAYS[d.getDay()]}) 09:00`}
function kstDate(iso){const t=new Date(iso);return new Date(t.getTime()+(t.getTimezoneOffset()+540)*60000)}

// ---------- 이벤트 ----------
document.addEventListener("click",e=>{
  const tb=e.target.closest(".tfs button");if(tb){const box=tb.closest(".chart");box.dataset.tf=tb.dataset.tf;box.querySelectorAll(".tfs button").forEach(b=>b.setAttribute("aria-pressed",b===tb));if(box._chart)box._chart.show(tb.dataset.tf);return}
  const ft=e.target.closest(".fit");if(ft){const ch=ft.closest(".chart")._chart;if(ch)ch.fit();return}
  if(!META)return;
  const mb=e.target.closest("#mkt button");if(mb){S.mkt=mb.dataset.v;render();return}
  const md=e.target.closest("#mode button");if(md){S.mode=md.dataset.v;render();return}
  const sg=e.target.closest("#sigs .tog");if(sg){const k=sg.dataset.k;S.sig.has(k)?S.sig.delete(k):S.sig.add(k);render();return}
  const cb=e.target.closest(".combo");if(cb){S.sig=new Set(cb.dataset.c.split("+"));S.mode="and";render();document.getElementById("list").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion:reduce)").matches?"auto":"smooth",block:"start"});return}
});
document.getElementById("cap").addEventListener("change",e=>{S.cap=e.target.value;if(META)render()});
document.getElementById("sort").addEventListener("change",e=>{S.sort=e.target.value;if(META)render()});
function retheme(){const C=colors();for(const ch of CHARTS){ch.c.applyOptions(themeOpts(C));ch.candle.applyOptions({upColor:C.up,downColor:C.dn,borderUpColor:C.up,borderDownColor:C.dn,wickUpColor:C.up,wickDownColor:C.dn});ch.rsi.applyOptions({color:C.ink});ch.show(ch.tf,true)}}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",retheme);
new MutationObserver(retheme).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});

// ---------- 카카오 연결 도우미 ----------
(function(){
  const self=location.origin+location.pathname;
  document.getElementById("selfurl").textContent=self;
  const inp=document.getElementById("krest"),a=document.getElementById("kauth");
  const upd=()=>{const k=inp.value.trim();a.href=k?`https://kauth.kakao.com/oauth/authorize?client_id=${encodeURIComponent(k)}&redirect_uri=${encodeURIComponent(self)}&response_type=code&scope=talk_message`:"#"};
  inp.addEventListener("input",upd);a.addEventListener("click",e=>{if(!inp.value.trim()){e.preventDefault();inp.focus()}});
  const q=new URLSearchParams(location.search),code=q.get("code"),err=q.get("error");
  if(code||err){
    const box=document.getElementById("kcode");box.hidden=false;
    if(err){box.querySelector("b").textContent="카카오 로그인이 취소되었거나 실패했습니다";document.getElementById("kcodeval").textContent=q.get("error_description")||err;document.getElementById("kcopy").hidden=true}
    else document.getElementById("kcodeval").textContent=code;
    const m=location.hostname.match(/^([^.]+)\.github\.io$/),repo=location.pathname.split("/").filter(Boolean)[0];
    if(m&&repo){const g=document.getElementById("kgo");g.href=`https://github.com/${m[1]}/${repo}/actions/workflows/kakao-setup.yml`;g.hidden=false}
    document.getElementById("kcopy").addEventListener("click",ev=>{const b=ev.currentTarget;navigator.clipboard?.writeText(code).then(()=>{b.textContent="복사됨"},()=>{const r=document.createRange();r.selectNodeContents(document.getElementById("kcodeval"));const s=getSelection();s.removeAllRanges();s.addRange(r);b.textContent="선택됨 · 복사하세요"})});
    try{history.replaceState(null,"",location.pathname)}catch(e){}
  }
})();

// ---------- 시작 ----------
function load(json){
  META=json;
  DATA=json.items.map((r,idx)=>({...r,idx}));
  const a=kstDate(json.asOf),nx=new Date(a);nx.setDate(nx.getDate()+1);
  document.getElementById("asof").textContent=stamp(a)+" 마감";
  document.getElementById("next").textContent=stamp(nx)+" 무렵";
  const st=document.getElementById("status");
  if(json.demo)st.innerHTML="<b>데모 데이터</b> · 가격·거래량·신호는 모두 가상입니다. GitHub Actions에서 실제 실행을 한 번 돌리면 실시세로 바뀝니다.";
  else{st.textContent=`실시세 · ${json.generated} 생성 · 스캔 미국 ${json.scanned.US} · 국내 ${json.scanned.KR} · 코인 ${json.scanned.CR}종목`;st.className="bar-note live"}
  render();
}
fetch("results.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}).then(load).catch(()=>{
  document.getElementById("status").innerHTML="<b>결과 파일을 불러오지 못했습니다.</b> 저장소 Actions 탭에서 daily-screener를 한 번 실행하고, Settings → Pages의 Source가 GitHub Actions인지 확인해 주세요.";
  document.getElementById("top5").innerHTML=`<div class="empty">아직 표시할 결과가 없습니다.</div>`;
});
