/* Плагин Лаборатории ИИ (PRIM, Выживаемость MAE/MFE, DSR и Экспорт Тензора) для Quant_Analytics_Dashboard_v2-2.html */
(function(){
  function normCdf(x){
    const t=1/(1+0.2316419*Math.abs(x)),d=0.3989423*Math.exp(-x*x/2);
    const p=d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));
    return x>0?1-p:p;
  }

  function computeDSR(tr, trials=24){
    const n=tr.length; if(n<10) return {sr:'0.00', dsr:'0.0', skew:'0.00', kurt:'3.00'};
    const rs=tr.map(t=>t.r||0), mu=rs.reduce((a,b)=>a+b,0)/n;
    const vr=rs.reduce((a,x)=>a+(x-mu)*(x-mu),0)/Math.max(1,n-1), sd=Math.sqrt(Math.max(1e-9,vr));
    const sr=mu/sd;
    const skew=rs.reduce((a,x)=>a+Math.pow((x-mu)/sd,3),0)/n;
    const kurt=rs.reduce((a,x)=>a+Math.pow((x-mu)/sd,4),0)/n;
    const z1=Math.sqrt(2*Math.log(Math.max(2,trials))), sr0=sd*((1-0.5772)*z1+0.5772*Math.sqrt(2*Math.log(trials*Math.E)))/Math.sqrt(n);
    const den=Math.sqrt(Math.max(1e-9, 1 - skew*sr + ((kurt-1)/4)*sr*sr));
    const dsr=normCdf(((sr-sr0)*Math.sqrt(n-1))/den)*100;
    return {sr:sr.toFixed(3), dsr:dsr.toFixed(1), skew:skew.toFixed(2), kurt:kurt.toFixed(2)};
  }

  function optimizeSurvival(tr, riskR){
    const v=tr.filter(t=>t.mae!=null&&t.mfe!=null);
    if(v.length<8) return {optStop:1.0, stopGain:0, optBe:1.0, beGain:0};
    let bestS=1.0, bestGain=0;
    for(let s=0.40; s<=1.10; s+=0.05){
      let gain=0;
      for(const t of v){
        if(t.mae>s){
          const newNet = -s*riskR - (t.fees+t.slip);
          gain += (newNet - t.net);
        }
      }
      if(gain>bestGain){ bestGain=gain; bestS=+s.toFixed(2); }
    }
    let bestBe=1.0, beGain=0;
    for(let m=0.75; m<=1.50; m+=0.15){
      let g=0;
      for(const t of v){ if(t.net<0 && t.mfe>=m) g += Math.abs(t.net); }
      if(g>beGain){ beGain=g; bestBe=+m.toFixed(2); }
    }
    return {optStop:bestS, stopGain:Math.round(bestGain), optBe:bestBe, beGain:Math.round(beGain)};
  }

  function mineSubgroups(tr, riskR){
    const n=tr.length, mid=n>>1, minN=Math.max(5, Math.round(n*0.04));
    const map=new Map();
    tr.forEach((t,idx)=>{
      const crr=(t.fees+t.slip)/Math.max(1,riskR);
      const tags=[
        `Токен: ${t.token}`,
        `Сторона: ${t.dir==='long'?'Long':'Short'}`,
        t.sess!=null?`Сессия: ${SESS[t.sess].label}`:null,
        t.order?`Ордер: ${t.order}`:null,
        crr>0.12?'Трение CRR > 12%':'Трение CRR ≤ 12%'
      ].filter(Boolean);
      for(let i=0;i<tags.length;i++){
        add(tags[i], idx, t.net);
        for(let j=i+1;j<tags.length;j++) add(`${tags[i]} + ${tags[j]}`, idx, t.net);
      }
    });
    function add(k,idx,v){ if(!map.has(k)) map.set(k,[]); map.get(k).push([idx,v]); }
    const toxic=[], golden=[];
    for(const [rule, arr] of map){
      if(arr.length<minN || arr.length>n*0.85) continue;
      const h1=arr.filter(x=>x[0]<mid).map(x=>x[1]), h2=arr.filter(x=>x[0]>=mid).map(x=>x[1]);
      if(h1.length<2 || h2.length<2) continue;
      const s1=h1.reduce((a,b)=>a+b,0), s2=h2.reduce((a,b)=>a+b,0), tot=s1+s2;
      const avg=tot/arr.length, wins=arr.filter(x=>x[1]>0).length;
      const item={rule, n:arr.length, tot:Math.round(tot), avg:avg.toFixed(1), wr:Math.round(wins/arr.length*100)};
      if(s1<0 && s2<0 && tot<0) toxic.push(item);
      else if(s1>0 && s2>0 && tot>0) golden.push(item);
    }
    toxic.sort((a,b)=>a.tot-b.tot); golden.sort((a,b)=>b.tot-a.tot);
    return {toxic:toxic.slice(0,5), golden:golden.slice(0,5)};
  }

  function renderAiLab(){
    const el=document.getElementById('view-ailab'); if(!el) return;
    const tr=S.view, st=S.st, riskR=S.flags.riskR||100;
    const dsr=computeDSR(tr), surv=optimizeSurvival(tr, riskR), sg=mineSubgroups(tr, riskR);
    const avgCrr = tr.length ? (st.costs / (tr.length * riskR) * 100) : 0;
    const makerSave = Math.round(st.slip * 0.85 + st.fees * 0.55);

    el.innerHTML=`<div class="grid">
      <div class="s12"><div class="tiles">
        <div class="tile"><div class="lbl">Дефлированный Шарп (DSR)</div><div class="val ${+dsr.dsr>=80?'up':+dsr.dsr>=50?'warn':'down'}">${dsr.dsr}%</div><div class="lbl">SR=${dsr.sr}, Skew=${dsr.skew}, Kurt=${dsr.kurt}</div></div>
        <div class="tile"><div class="lbl">Налог трения (CRR на 1R)</div><div class="val ${avgCrr<=6?'up':avgCrr<=15?'warn':'down'}">${avgCrr.toFixed(1)}%</div><div class="lbl">Норма ≤ 6.0% от риска сделки</div></div>
        <div class="tile"><div class="lbl">Оптимальный Стоп (Каплан-Мейер)</div><div class="val up">−${surv.optStop} R</div><div class="lbl">Экономия: ${fmtUsd0(surv.stopGain,{sign:1})}</div></div>
        <div class="tile"><div class="lbl">Переход Market → Maker Limit</div><div class="val up">${fmtUsd0(makerSave,{sign:1})}</div><div class="lbl">ОжидаемыйNet: ${fmtUsd0(st.net+makerSave,{sign:1})}</div></div>
      </div></div>
      <article class="card s6">
        <div class="card-h"><div><h3>🟢 Золотые кластеры (PRIM Split-Half)</h3><div class="sub">Правила, дающие плюс в обеих половинах истории</div></div></div>
        <div class="tbl-wrap"><table><thead><tr><th>Закономерность (Условие)</th><th class="r">Сделок</th><th class="r">WinRate</th><th class="r">Чистый PnL</th></tr></thead><tbody>
          ${sg.golden.length?sg.golden.map(g=>`<tr><td><b>${esc(g.rule)}</b></td><td class="r">${g.n}</td><td class="r">${g.wr}%</td><td class="r up"><b>+${fmtUsd0(g.tot)}</b></td></tr>`).join(''):'<tr><td colspan="4" class="mute">Нет устойчивых плюсовых подгрупп</td></tr>'}
        </tbody></table></div>
      </article>
      <article class="card s6">
        <div class="card-h"><div><h3>🔴 Токсичные кластеры (Кандидаты на блокировку)</h3><div class="sub">Устойчивые генераторы убытка в обеих половинах истории</div></div></div>
        <div class="tbl-wrap"><table><thead><tr><th>Закономерность (Условие)</th><th class="r">Сделок</th><th class="r">WinRate</th><th class="r">Убыток</th></tr></thead><tbody>
          ${sg.toxic.length?sg.toxic.map(g=>`<tr><td><b>${esc(g.rule)}</b></td><td class="r">${g.n}</td><td class="r">${g.wr}%</td><td class="r down"><b>${fmtUsd0(g.tot)}</b></td></tr>`).join(''):'<tr><td colspan="4" class="mute">Нет устойчивых токсичных подгрупп</td></tr>'}
        </tbody></table></div>
      </article>
      <article class="card hero s12">
        <div class="card-h"><div><h3>🤖 Экспорт математического слепка для обучения ИИ</h3><div class="sub">Выгружает сжатый JSON-тензор (DSR, квантили выживаемости MAE/MFE, CRR, правила PRIM)</div></div>
        <button class="btn primary" type="button" id="btnExportAiTensor">Скачать ai_research_tensor.json</button></div>
      </article>
    </div>`;

    document.getElementById('btnExportAiTensor').onclick=()=>{
      const payload={generated_at:new Date().toISOString(),total_trades:tr.length,net_pnl:st.net,gross_pnl:st.gross,costs:st.costs,avg_crr_pct:+avgCrr.toFixed(2),dsr,survival_mae_mfe:surv,prim_subgroups:sg};
      download('ai_research_tensor.json',JSON.stringify(payload,null,2),'application/json');
    };
  }

  window.QuantLabV16 = { computeDSR, optimizeSurvival, mineSubgroups, renderAiLab };
})();