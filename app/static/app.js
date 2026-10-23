'use strict';
const $ = (s, node=document) => node.querySelector(s);
const $$ = (s, node=document) => [...node.querySelectorAll(s)];
const form = $('#scenario-form');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const currency = n => n == null ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(n));
const number = n => new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(Number(n));
const field = name => form.elements.namedItem(name);
let params = null, lastResult = null, generation = 0, timer, toastTimer, editingIndex = null;
let saved = [];
try { const value=JSON.parse(localStorage.getItem('eppgg.scenarios.v1') || '[]'); if (Array.isArray(value)) saved=value.slice(0,3).filter(s=>s && typeof s==='object' && !Array.isArray(s)); } catch { /* corrupt local storage is never executed */ }

function toast(message) { $('#toast').textContent=message; $('#toast').classList.remove('hidden'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('#toast').classList.add('hidden'),4200); }
async function api(path, body) {
  const response=await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!response.ok) {
    let detail; try { detail=(await response.json()).detail; } catch { detail='O serviço não respondeu. Tente novamente.'; }
    if (Array.isArray(detail)) detail=detail.map(x=>`${x.loc?.slice(1).join('.') || 'Entrada'}: ${x.msg}`).join(' · ');
    throw new Error(typeof detail==='string' ? detail : 'Não foi possível concluir a operação.');
  }
  return response.json();
}
function showTab(id) {
  $$('.view').forEach(v=>v.classList.toggle('active',v.id===id));
  $$('.tab').forEach(t=>{t.classList.toggle('active',t.dataset.tab===id); if(t.dataset.tab===id)t.setAttribute('aria-current','page');else t.removeAttribute('aria-current');});
  if(id==='sources') loadSources();
  if(id==='compare') renderSaved();
}
$$('.tab').forEach(t=>t.addEventListener('click',()=>showTab(t.dataset.tab)));
$('#view-sources').addEventListener('click',()=>showTab('sources'));

function options(select, values, old) { select.replaceChildren(...values.map(v=>new Option(v,v))); if(values.includes(old))select.value=old; }
function positionOptions(levelId,gradeId) {
  const levels=[...new Set((params?.positions || []).map(p=>p.level))];
  const level=$(levelId), grade=$(gradeId), old=level.value;
  options(level,levels,old); updateGrades(levelId,gradeId);
}
function updateGrades(levelId,gradeId) { const level=$(levelId), grade=$(gradeId); options(grade,(params?.positions || []).filter(p=>p.level===level.value).map(p=>p.grade),grade.value); }
async function loadParameters() {
  const request=++generation;
  params=null; lastResult=null;
  $('#result').replaceChildren();
  $('#version-label').textContent='Carregando parâmetros…';
  try {
    const data=await api(`/api/parameters?competence=${encodeURIComponent(field('competence').value)}&mode=${encodeURIComponent(field('mode').value)}`);
    if(request!==generation)return;
    params=data;
    positionOptions('#level','#grade'); positionOptions('#future-level','#future-grade');
    const commission=$('#commission'), old=commission.value;
    commission.replaceChildren(new Option('Selecione um cargo',''),...data.commissions.map(c=>new Option(`${c.code} · ${currency(c.amount)}`,c.code)));
    if(data.commissions.some(c=>c.code===old))commission.value=old;
    const fn=$('#function'),oldFunction=fn.value;
    fn.replaceChildren(new Option('Nenhuma',''),...(data.functions || []).map(f=>new Option(`${f.code} · ${currency(f.amount)}`,f.code)));
    if((data.functions || []).some(f=>f.code===oldFunction))fn.value=oldFunction;
    updateCommissionChoices();
    $('#version-label').textContent=`${data.version} · ${data.status==='demo'?'Dados fictícios':data.status==='real'?'Remuneração real · bruto':'Parâmetros auditados'}`;
    $('#mode-notice').textContent=data.status==='demo'?' Os valores do modo demonstrativo são fictícios. Use Reais · bruto para a remuneração da carreira.':data.status==='real'?' Vencimentos, pontos GDPI, cargos e funções de fontes oficiais. Descontos e líquido não apurados.':` Versão ${data.version}; confira fontes, enquadramentos e limites antes de usar os resultados.`;
    $('#calculation-error').classList.add('hidden');
    await calculate();
  } catch(error) {if(request!==generation)return;$('#calculate').disabled=false;$('#version-label').textContent='Nenhuma tabela disponível';$('#level').replaceChildren();$('#grade').replaceChildren();$('#future-level').replaceChildren();$('#future-grade').replaceChildren();showCalculationError(error);}
}
function beneficiaryRow(value={relationship:'child',age:10,special_condition:false}) {
  const div=document.createElement('div');div.className='mini-panel beneficiary';
  div.innerHTML=`<div class="field-row"><label>Parentesco<select class="relationship"><option value="child">Filho(a)</option><option value="spouse">Cônjuge</option><option value="parent">Pai/mãe</option><option value="sibling">Irmão(ã)</option></select></label><label>Idade<input class="beneficiary-age" type="number" min="0" max="120" value="${escape(value.age)}" required></label></div><label class="check"><input type="checkbox" class="special-condition" ${value.special_condition?'checked':''}> Condição especial</label><button type="button" class="text-button remove">Remover beneficiário</button>`;
  $('.relationship',div).value=value.relationship;
  $('.remove',div).addEventListener('click',()=>{div.remove();schedule();});
  $('#beneficiaries').append(div);
}
$('#add-beneficiary').addEventListener('click',()=>{if($$('.beneficiary').length>=30)return toast('Limite de 30 beneficiários.');beneficiaryRow();});
function rubricRow(value={name:'',amount:'0',nature:'earning',source:'Informado pelo usuário; incidências a conferir',tax:false,pension:false,health:false,vacation:false,thirteenth:false,proportional:false}) {
  const div=document.createElement('div');div.className='mini-panel rubric';
  div.innerHTML=`<label>Rubrica<input class="rubric-name-input" value="${escape(value.name)}" maxlength="100" required></label><div class="field-row"><label>Valor (R$)<input class="rubric-amount" type="number" min="0" step="0.01" value="${escape(value.amount)}" required></label><label>Natureza<select class="rubric-nature"><option value="earning">Provento</option><option value="deduction">Consignação</option></select></label></div><div class="flag-grid">${[['tax','IR'],['pension','RPPS'],['health','IPSEMG'],['vacation','Férias'],['thirteenth','13º'],['proportional','Proporcional']].map(([key,label])=>`<label class="check"><input type="checkbox" data-flag="${key}" ${value[key]?'checked':''}>${label}</label>`).join('')}</div><label>Fonte / fundamento<input class="rubric-source" value="${escape(value.source)}" maxlength="500" required></label><button type="button" class="text-button remove">Remover rubrica</button>`;
  $('.rubric-nature',div).value=value.nature;
  $('.remove',div).addEventListener('click',()=>{div.remove();schedule();});
  $('#rubrics').append(div);
}
$('#add-rubric').addEventListener('click',()=>{if($$('.rubric').length>=50)return toast('Limite de 50 rubricas.');rubricRow();});
function scenario() {
  const s={};
  for(const name of ['name','competence','mode','level','grade','adi','ai','fraction','gdpi_evaluation','remuneration_option','copay','alimony','other_deductions'])s[name]=field(name).value;
  for(const name of ['gdpi_eligible','commission_pension','function_pension','capped_pension','complementary_deductible','health_enrolled','special_health','alimony_deductible','project_annual'])s[name]=field(name).checked;
  for(const name of ['age','tax_dependents'])s[name]=Number(field(name).value);
  s.commission=field('commission').value || null;
  s.function=field('function').value || null;
  s.complementary_rate=String(Number(field('complementary_percent').value)/100);
  s.beneficiaries=$$('.beneficiary').map(div=>({relationship:$('.relationship',div).value,age:Number($('.beneficiary-age',div).value),special_condition:$('.special-condition',div).checked}));
  s.rubrics=$$('.rubric').map(div=>({name:$('.rubric-name-input',div).value,amount:$('.rubric-amount',div).value,nature:$('.rubric-nature',div).value,source:$('.rubric-source',div).value,...Object.fromEntries($$('[data-flag]',div).map(i=>[i.dataset.flag,i.checked]))}));
  return s;
}
function schedule() {clearTimeout(timer);timer=setTimeout(()=>{if(params && form.checkValidity())calculate();},400);}
form.addEventListener('input',event=>{if(!['competence','mode','level','grade'].includes(event.target.name))schedule();});
form.addEventListener('change',event=>{if(event.target.name==='commission')updateCommissionChoices();if(['competence','mode'].includes(event.target.name))loadParameters();else if(event.target.name==='level'){updateGrades('#level','#grade');schedule();}else schedule();});
form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);calculate();});
$('#future-level').addEventListener('change',()=>updateGrades('#future-level','#future-grade'));
function showCalculationError(error) {$('#calculation-error').textContent=error.message;$('#calculation-error').classList.remove('hidden');$('#result').innerHTML='<div class="empty panel">Ajuste os parâmetros indicados para obter uma nova simulação.</div>';lastResult=null;}
async function calculate() {
  if(!params)return;
  const request=++generation;
  $('#calculate').disabled=true;
  try {const result=await api('/api/calculate',scenario());if(request!==generation)return;lastResult=result;$('#calculation-error').classList.add('hidden');renderResult(result);}
  catch(error){if(request===generation)showCalculationError(error);}
  finally{if(request===generation)$('#calculate').disabled=false;}
}
function metric(label,value){return `<div class="metric-row"><span>${escape(label)}</span><strong>${escape(value)}</strong></div>`;}
function renderResult(r) {
  if(r.parameters.status==='real')return renderRealResult(r);
  const m=r.monthly, t=m.income_tax, g=r.gdpi;
  const row=(name,amount,source,negative=false,incidence='')=>`<tr><td><span class="rubric-name">${escape(name)}</span>${source?`<span class="source-small">${escape(source)}</span>`:''}${incidence?`<span class="incidences">${escape(incidence)}</span>`:''}</td><td class="amount ${negative?'deduction':''}">${negative?'− ':''}${currency(amount)}</td></tr>`;
  const rows=m.earnings.map(e=>row(e.name,e.amount,e.source,false,[e.tax?'IR':'',e.pension?'RPPS':'',e.health?'IPSEMG':'',e.vacation?'Férias':'',e.thirteenth?'13º':''].filter(Boolean).join(' · '))).join('');
  const deductions=[['RPPS · contribuição progressiva',m.pension.amount,r.parameters.sources.pension],['Previdência complementar',m.complementary,'Percentual informado sobre o excedente ao teto'],['IPSEMG Saúde',m.health.amount,r.parameters.sources.health],['Coparticipação IPSEMG',m.health.copay,'Valor informado'],['IRRF',t.amount,r.parameters.sources.tax],['Pensão alimentícia',m.alimony,'Valor informado por folha; dedução condicionada ao enquadramento'],['Outros descontos e consignações',m.other_deductions,'Valores informados após as bases legais']].filter(([,value])=>Number(value)!==0).map(([name,value,source])=>row(name,value,source,true)).join('');
  const annual=r.annual;
  $('#result').innerHTML=`<div class="summary-grid"><div class="stat"><span class="stat-label"><i class="dot"></i> Remuneração bruta</span><span class="stat-value">${currency(m.gross)}</span><span class="stat-sub">Proventos da competência</span></div><div class="stat"><span class="stat-label"><i class="dot gold"></i> Descontos totais</span><span class="stat-value">${currency(m.deductions)}</span><span class="stat-sub">Contribuições e deduções</span></div><div class="stat net"><span class="stat-label">Seu líquido mensal ↗</span><span class="stat-value">${currency(m.net)}</span><span class="stat-sub">Estimativa ${r.parameters.status==='demo'?'demonstrativa':'da competência'}</span></div></div>
+  <div class="panel"><div class="result-title"><div><h2>Seu demonstrativo</h2><p>${escape(r.scenario.name)} · ${escape(r.scenario.competence)} · Nível ${escape(r.scenario.level)}, grau ${escape(r.scenario.grade)}</p></div><span class="pill ${r.parameters.status==='verified'?'verified':''}">${r.parameters.status==='demo'?'DADOS FICTÍCIOS':escape(r.parameters.status.toUpperCase())}</span></div><div class="table-scroll"><table><thead><tr><th>RUBRICA / FUNDAMENTO</th><th>VALOR MENSAL</th></tr></thead><tbody>${rows}${deductions}<tr class="total-row"><td>Líquido estimado</td><td class="amount">${currency(m.net)}</td></tr></tbody></table></div><div class="export-bar"><span>Memória aberta. Cada base, cada incidência.</span><div class="actions"><button class="secondary export" data-format="csv">↓ CSV</button><button class="secondary export" data-format="json">↓ Memória JSON</button></div></div></div>
+  <div class="subgrid"><div class="panel"><div class="small-title">DESEMPENHO & PRODUTIVIDADE</div><h2>Sua GDPI em detalhe</h2><div class="big-inline">${currency(g.actual)}</div>${metric('Fator de avaliação',number(Number(g.evaluation)*100)+'%')}${metric('Teto com notas de 100%',currency(g.ceiling))}${metric('Pontos × fator × VBref',`${number(g.effective_points ?? g.points)} × ${g.factor} × ${currency(g.reference_salary)}`)}<p class="field-help">${escape(g.formula)}</p>${!g.eligible?'<div class="callout">GDPI zerada: elegibilidade ou nota mínima individual não atendida.</div>':''}</div><div class="panel"><div class="small-title">OLHANDO PARA O ANO</div><h2>Além do salário mensal</h2>${annual?`<div class="big-inline">${currency(annual.net)}</div><p class="field-help">Líquido anual em hipótese estática</p>${metric('13º líquido (folha separada)',currency(annual.thirteenth.net))}${metric('Férias + terço · líquido da folha',currency(annual.vacation.net))}${metric('Diferença líquida da folha de férias',currency(annual.vacation_increment_net))}<p class="field-help">${escape(annual.assumptions)}</p>`:'<p>Projeção anual desativada neste cenário.</p>'}</div></div>
+  <div class="panel breakdown"><h2>Por dentro dos descontos</h2><details><summary>Previdência · base ${currency(m.pension.base)}</summary>${metric('Remuneração contributiva antes do teto',currency(m.bases.pension))}${Number(m.pension.effective_reference_addition)?metric('Base do efetivo mantida sem pagamento',currency(m.pension.effective_reference_addition)):''}${m.pension.bands.map(b=>metric(`${currency(b.from)} a ${b.until==null?'sem limite':currency(b.until)} · ${number(Number(b.rate)*100)}%`,`${currency(b.base)} × ${number(Number(b.rate)*100)}%`)).join('')}${metric('Contribuição após soma das faixas',currency(m.pension.amount))}</details><details><summary>Imposto de renda · ${t.method==='legal'?'deduções legais':'desconto simplificado'} mais vantajoso</summary>${metric('Rendimento tributável (referência da redução)',currency(t.income))}${metric('Deduções legais',currency(t.legal_deductions))}${metric('Simplificado disponível',currency(t.simplified_deduction))}${metric('Dedução escolhida',currency(t.deduction))}${metric('Base após deduções',currency(t.base))}${metric('Alíquota / parcela a deduzir',`${number(Number(t.rate)*100)}% / ${currency(t.bracket_deduction)}`)}${metric('IR pela tabela',currency(t.before_reduction))}${metric('Redução legal',currency(t.reduction))}${metric('IRRF',currency(t.amount))}<div class="callout">A redução considera o rendimento tributável antes das deduções. IPSEMG Saúde não reduz a base mensal do IR.</div></details><details><summary>IPSEMG · base ${currency(m.bases.health)}</summary>${m.health.beneficiaries.map(b=>metric(b.name,currency(b.amount))).join('')}${!m.health.beneficiaries.length?'<p class="field-help">Sem desconto de assistência nesta folha.</p>':''}</details>${annual?`<details><summary>Memória das folhas de férias e 13º</summary>${['vacation','thirteenth'].map(k=>`<h3>${k==='vacation'?'Férias com terço':'13º separado'}</h3>${metric('Bruto',currency(annual[k].gross))}${metric('RPPS',currency(annual[k].pension.amount))}${metric('IPSEMG',currency(annual[k].health.amount))}${metric('IRRF exclusivo desta folha',currency(annual[k].income_tax.amount))}${metric('Demais descontos',currency(Number(annual[k].deductions)-Number(annual[k].pension.amount)-Number(annual[k].health.amount)-Number(annual[k].income_tax.amount)))}${metric('Líquido',currency(annual[k].net))}`).join('')}<p class="field-help">Detalhes de incidências e rubricas constam da exportação JSON.</p></details>`:''}<details><summary>Versão, arredondamento e ressalvas</summary>${metric('Conjunto de parâmetros',r.parameters.version)}${metric('Vigência',`${r.parameters.valid_from} a ${r.parameters.valid_until}`)}<p class="field-help">${escape(r.rounding)}</p><ul class="warning-list">${r.warnings.map(w=>`<li>${escape(w)}</li>`).join('')}</ul></details></div>`.replace(/^\+/gm,'');
  $$('.export').forEach(b=>b.addEventListener('click',()=>exportResult(b.dataset.format)));
}
async function exportResult(kind) {
  if(!lastResult)return toast('Calcule um cenário válido antes de exportar.');
  try {
    const response=await fetch('/api/export/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(lastResult.scenario)});
    if(!response.ok)throw new Error('Não foi possível exportar. Recalcule e tente novamente.');
    download(await response.blob(),'eppgg-memoria.'+kind);
  } catch(error){toast(error.message);}
}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function persist(){try{localStorage.setItem('eppgg.scenarios.v1',JSON.stringify(saved));}catch{toast('O navegador não permitiu gravar cenários. Exporte o JSON para guardá-los.');}renderSaved();}
$('#save').addEventListener('click',async()=>{if(saved.length>=3 && editingIndex===null)return toast('Você já tem três cenários. Exclua um para salvar outro.');try{const s=scenario();await api('/api/calculate',s);if(editingIndex===null)saved.push(s);else saved[editingIndex]=s;editingIndex=null;$('#save').textContent='＋ Salvar cenário';persist();$('#comparison-result').replaceChildren();toast('Cenário salvo neste navegador.');}catch(error){toast(error.message);}});
function renderSaved(){
  $('#saved-count').textContent=saved.length;
  $('#saved-list').innerHTML=saved.length?saved.map((s,i)=>`<article class="panel saved-card"><span class="pill">${escape(s.mode==='demo'?'DEMONSTRATIVO':s.mode==='real'?'REMUNERAÇÃO REAL':'FOLHA AUDITADA')}</span><h3>${escape(s.name)}</h3><p>${escape(s.competence)} · Nível ${escape(s.level)}, grau ${escape(s.grade)}<br>ADI ${escape(s.adi)}% · AI ${escape(s.ai)}%</p><div class="actions"><button class="secondary load-scenario" data-index="${i}">Editar</button><button class="secondary duplicate-scenario" data-index="${i}">Duplicar</button><button class="text-button delete-scenario" data-index="${i}">Excluir</button></div></article>`).join(''):'<div class="empty panel">Nenhum cenário salvo. Monte sua simulação e clique em “Salvar cenário”.</div>';
  $$('.delete-scenario').forEach(b=>b.addEventListener('click',()=>{saved.splice(Number(b.dataset.index),1);editingIndex=null;$('#save').textContent='＋ Salvar cenário';persist();$('#comparison-result').replaceChildren();}));
  $$('.duplicate-scenario').forEach(b=>b.addEventListener('click',()=>{if(saved.length>=3)return toast('O comparador admite até três cenários.');saved.push({...structuredClone(saved[Number(b.dataset.index)]),name:(saved[Number(b.dataset.index)].name+' · cópia').slice(0,80)});persist();}));
  $$('.load-scenario').forEach(b=>b.addEventListener('click',()=>{editingIndex=Number(b.dataset.index);$('#save').textContent='Salvar alterações';loadScenario(saved[editingIndex]);}));
}
async function loadScenario(s){
  clearTimeout(timer);
  for(const [key,value] of Object.entries(s)){const input=field(key);if(!input || ['level','grade','commission','function'].includes(key))continue;if(input.type==='checkbox')input.checked=Boolean(value);else input.value=value;}
  field('complementary_percent').value=Number(s.complementary_rate || 0)*100;
  $('#beneficiaries').replaceChildren();(s.beneficiaries || []).forEach(beneficiaryRow);
  $('#rubrics').replaceChildren();(s.rubrics || []).forEach(rubricRow);
  showTab('calculator');await loadParameters();
  if(params){field('level').value=s.level;updateGrades('#level','#grade');field('grade').value=s.grade;field('commission').value=s.commission || '';field('function').value=s.function || '';updateCommissionChoices();await calculate();}
}
function comparisonMarkup(r) {
  const metrics=[['Bruto mensal',x=>currency(x.monthly.gross)],['Diferença bruta vs. primeiro',x=>currency(x.difference.gross)],['RPPS',x=>currency(x.monthly.pension?.amount)],['IPSEMG',x=>currency(x.monthly.health?.amount)],['IRRF',x=>currency(x.monthly.income_tax?.amount)],['Líquido mensal',x=>currency(x.monthly.net)],['Líquido anual estático',x=>currency(x.annual?.net)],['Diferença mensal vs. primeiro',x=>currency(x.difference.monthly)],['Variação mensal',x=>x.difference.monthly_percent==null?'—':number(x.difference.monthly_percent)+'%'],['Diferença anual vs. primeiro',x=>currency(x.difference.annual)],['Variação anual',x=>x.difference.annual_percent==null?'—':number(x.difference.annual_percent)+'%']];
  return `<div class="panel comparison-table"><div class="table-scroll"><table><thead><tr><th>INDICADOR</th>${r.results.map((x,i)=>`<th>${escape(x.scenario.name)}${r.best_monthly===null && i===r.best_gross?'<br><span>Maior bruto · líquido não apurado</span>':''}${i===r.best_monthly?'<br><span class="best">↑ Maior líquido mensal</span>':''}${i===r.best_annual?'<br><span class="best">↑ Maior líquido anual</span>':''}</th>`).join('')}</tr></thead><tbody>${metrics.map(([label,get])=>`<tr><td>${label}</td>${r.results.map(x=>`<td>${get(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="field-help">Mesma competência; projeção anual estática. Empates indicam a primeira opção. ${r.results.some(x=>x.parameters.status==='demo')?'Resultados com dados fictícios.':''}</p></div>`;
}
$('#run-compare').addEventListener('click',async()=>{try{$('#comparison-result').innerHTML=comparisonMarkup(await api('/api/compare',{scenarios:saved}));}catch(error){$('#comparison-result').innerHTML=`<div class="error" role="alert">${escape(error.message)}</div>`;}});
$('#compare-options').addEventListener('click',async()=>{try{const result=await api('/api/commission-options',scenario());showTab('compare');$('#comparison-result').innerHTML=comparisonMarkup(result);}catch(error){toast(error.message);}});
$('#import-scenario').addEventListener('click',()=>$('#import-file').click());
$('#import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>1024*1024)throw new Error('Arquivo excede 1 MB.');const data=JSON.parse(await file.text()),s=data.scenario || data;if(saved.length>=3)throw new Error('Exclua um cenário antes de importar.');const valid=await api('/api/calculate',s);saved.push(valid.scenario);persist();toast('Cenário validado e importado.');}catch(error){toast(error.message);}event.target.value='';});
$('#reset').addEventListener('click',()=>{clearTimeout(timer);editingIndex=null;$('#save').textContent='＋ Salvar cenário';form.reset();$('#beneficiaries').replaceChildren();$('#rubrics').replaceChildren();loadParameters();});
$('#project-career').addEventListener('click',async()=>{try{const r=await api('/api/career',{scenario:scenario(),future_level:$('#future-level').value,future_grade:$('#future-grade').value,years:Number($('#future-years').value)});const max=Math.max(1,...r.series.map(x=>Math.abs(Number(x.accumulated_difference))));$('#career-result').innerHTML=`<div class="panel"><h2>Sua perspectiva de evolução</h2>${metric('Diferença bruta mensal',currency(r.gross_monthly_difference))}${metric('Diferença bruta anual',currency(r.gross_annual_difference))}${metric('Diferença líquida mensal',currency(r.monthly_difference))}${metric('Diferença anual estática',currency(r.annual_difference))}${r.series.every(x=>x.accumulated_difference!=null)?`<svg class="chart" viewBox="0 0 720 220" role="img" aria-label="Diferença líquida acumulada por ano">${r.series.map((x,i)=>{const w=650/r.series.length,h=Math.abs(Number(x.accumulated_difference))/max*135;return `<rect class="chart-bar ${i===r.series.length-1?'accent':''}" x="${40+i*w}" y="${170-h}" width="${w*.65}" height="${h}" rx="4"/><text x="${40+i*w}" y="195">${x.year}a</text>`;}).join('')}</svg>`:''}<div class="table-scroll"><table><thead><tr><th>ANO</th><th>DIFERENÇA ACUMULADA · ${r.monthly_difference===null?'BRUTA':'LÍQUIDA'}</th></tr></thead><tbody>${r.series.map(x=>`<tr><td>${x.year}</td><td>${currency(x.accumulated_difference ?? x.accumulated_gross_difference)}</td></tr>`).join('')}</tbody></table></div><p class="field-help">${escape(r.assumptions)} Barras mostram a magnitude; a tabela preserva o sinal das diferenças.</p></div>`;}catch(error){$('#career-result').innerHTML=`<div class="error" role="alert">${escape(error.message)}</div>`;}});
$('#act-form').addEventListener('submit',async event=>{event.preventDefault();try{const f=event.target,r={scenario:scenario()};for(const key of ['requirement_date','protocol_date','publication_date','financial_date','level_start','blocked_until'])r[key]=f.elements.namedItem(key).value || null;for(const key of ['probation_complete','satisfactory','in_effective_exercise'])r[key]=f.elements.namedItem(key).checked;for(const key of ['progression_balance','promotion_balance','validated_event_points'])r[key]=f.elements.namedItem(key).value;r.prior_progressions_this_year=Number(f.elements.namedItem('prior_progressions_this_year').value);const result=await api('/api/career/act',r);$('#act-result').innerHTML=`<div class="callout"><strong>${escape({promotion:'Promoção',progression:'Progressão',none:'Sem movimentação elegível'}[result.act])}</strong> · Nível ${escape(result.target.level)}, grau ${escape(result.target.grade)}${metric('Saldo progressão',number(result.progression_balance))}${metric('Saldo promoção',number(result.promotion_balance))}${metric('Pontos consumidos',number(result.points_used))}${metric('Interstício completa em',result.interstice_completed_on)}<p>${escape(result.warning)}</p><p class="field-help">${escape(result.source)}</p></div>`;}catch(error){$('#act-result').innerHTML=`<div class="error" role="alert">${escape(error.message)}</div>`;}});
$('#calculate-retro').addEventListener('click',async()=>{try{const entries=JSON.parse($('#retro-input').value).map(pair=>pair.map(s=>s.scenario || s));const r=await api('/api/retroactive',{entries});$('#retro-result').innerHTML=`<div class="callout">${r.entries.map(e=>metric(e.competence,currency(e.net_difference ?? e.gross_difference))).join('')}${metric('Total das diferenças brutas',currency(r.total_gross_difference))}${metric('Total das diferenças líquidas',currency(r.total_net_difference))}<p>${escape(r.warning)}</p></div>`;}catch(error){$('#retro-result').innerHTML=`<div class="error" role="alert">${escape(error.message)}</div>`;}});
async function loadSources(){try{const r=await api('/api/sources');$('#sources-content').innerHTML=`<div class="sources-grid"><div class="panel"><h2>Conjuntos cadastrados</h2>${r.versions.map(v=>`<h3>${escape(v.version)} <span class="pill">${escape(v.status)}</span></h3><p>${escape(v.source)}</p>${metric('Vigência',`${v.valid_from} a ${v.valid_until}`)}${metric(v.status==='real'?'Conferência das fontes':'Auditoria',v.verified_at || 'Pendente')}<ul class="warning-list">${(v.notes || []).map(n=>`<li>${escape(n)}</li>`).join('')}</ul>`).join('')}<div class="callout">As tabelas remuneratórias reais de 2026 são carregadas automaticamente na implantação. Parâmetros completos de descontos exigem importação e conferência administrativa.</div></div><div class="panel"><h2>Antes de usar para folha</h2><ul>${r.pending.map(n=>`<li>${escape(n)}</li>`).join('')}</ul><h3>Regras históricas identificadas nos anexos</h3><ul>${r.historical_findings.map(n=>`<li>${escape(n)}</li>`).join('')}</ul></div><div class="panel"><h2>Acervo recebido</h2><p>Documentos preservados em <code>docs/legislacao/</code> no repositório. Textos históricos não atestam vigência em 2026.</p><ul class="document-list">${r.attachments.map(a=>`<li>${escape(a.file)}<details><summary>Integridade SHA-256</summary><code class="code">${escape(a.sha256)}</code></details></li>`).join('')}</ul></div><div class="panel"><h2>Como interpretar os resultados</h2><p>A memória registra parâmetros, fontes, incidências e arredondamento por rubrica. Exporte o JSON para conferir todas as folhas.</p><p>Reais · bruto utiliza a remuneração documentada nas fontes. Folha auditada continua bloqueada sem descontos conferidos; Demonstrativos mantém números fictícios para testes.</p><p>Não calcula RRA, múltiplos vínculos/fontes, isenções especiais, aposentadoria nem elegibilidade de títulos. A evolução detalhada recebe pontos já homologados e não automatiza concessões.</p><p>Cenários ficam no navegador, sem cadastro. Somente os parâmetros legais são persistidos no PostgreSQL/Neon.</p></div></div>`;await loadRealCatalog();}catch(error){$('#sources-content').innerHTML=`<div class="error">${escape(error.message)}</div>`;}}
renderSaved();loadParameters();

function updateCommissionChoices() {
  if(!params)return;
  const c=params.commissions.find(item=>item.code===field('commission').value);
  for(const option of field('remuneration_option').options) {
    option.disabled=option.value!=='none' && Boolean(c) && !c['allow_'+option.value];
  }
}

function renderRealResult(r) {
  const m=r.monthly,g=r.gdpi,a=r.annual;
  $('#result').innerHTML=`<div class="summary-grid"><div class="stat"><span class="stat-label">Remuneração bruta real</span><span class="stat-value">${currency(m.gross)}</span><span class="stat-sub">Valores publicados pela SEPLAG</span></div><div class="stat"><span class="stat-label">GDPI calculada</span><span class="stat-value">${currency(g.actual)}</span><span class="stat-sub">50% dos pontos · avaliações aplicadas</span></div><div class="stat net"><span class="stat-label">Líquido mensal</span><span class="stat-value">A conferir</span><span class="stat-sub">Descontos reais ainda não apurados</span></div></div>
<div class="panel"><div class="result-title"><div><h2>Remuneração com dados reais</h2><p>${escape(r.scenario.name)} · ${escape(r.scenario.competence)} · Nível ${escape(r.scenario.level)}, grau ${escape(r.scenario.grade)}</p></div><span class="pill verified">FONTES OFICIAIS</span></div><div class="table-scroll"><table><thead><tr><th>PROVENTO / FONTE</th><th>VALOR BRUTO</th></tr></thead><tbody>${m.earnings.map(row=>`<tr><td><span class="rubric-name">${escape(row.name)}</span><span class="source-small">${escape(row.source)}</span></td><td class="amount">${currency(row.amount)}</td></tr>`).join('')}<tr class="total-row"><td>Total bruto estimado</td><td>${currency(m.gross)}</td></tr></tbody></table></div><div class="callout">O bruto usa vencimentos, pontos GDPI e valores de cargos/funções reais. RPPS, IPSEMG, IRRF e demais descontos não foram aplicados neste modo. O total acima não é o valor líquido a receber.</div><div class="export-bar"><span>${escape(r.parameters.version)}</span><div class="actions"><button class="secondary export" data-format="csv">↓ CSV</button><button class="secondary export" data-format="json">↓ Memória JSON</button></div></div></div>
<div class="subgrid"><div class="panel"><h2>GDPI · regra legal aplicada</h2>${metric('Pontuação máxima do Anexo V',number(g.points))}${metric('Quota variável da pontuação',number(Number(g.point_share)*100)+'%')}${metric('Pontos utilizados na fórmula',number(g.effective_points))}${metric('Fator legal',g.factor)}${metric('VB referência · nível V, grau J',currency(g.reference_salary))}${metric('Resultado da avaliação',number(Number(g.evaluation)*100)+'%')}${metric('Teto com notas de 100%',currency(g.ceiling))}${metric('GDPI efetiva',currency(g.actual))}<p class="field-help">${escape(g.formula)}</p>${!g.eligible?'<div class="callout">GDPI zerada: nota mínima individual ou elegibilidade não atendida.</div>':''}</div><div class="panel"><h2>Projeções brutas</h2>${a?`${metric('13º bruto integral',currency(a.thirteenth.gross))}${metric('Folha de férias + terço · bruto',currency(a.vacation.gross))}${metric('Anual bruto estático',currency(a.gross))}<p class="field-help">${escape(a.assumptions)}</p>`:'<p>Projeção anual desativada.</p>'}<div class="callout">A opção A de comissão real depende de conferência do enquadramento e permanece indisponível. A opção B usa efetivo + 50% do cargo; funções FGD/FGI e GTE são parcelas integrais.</div></div></div>
<div class="panel breakdown"><h2>Fontes e limites da simulação</h2>${metric('Vigência disponibilizada',`${r.parameters.valid_from} a ${r.parameters.valid_until}`)}${metric('Conferência documental',r.parameters.verified_at)}<details><summary>Regras e ressalvas</summary><ul class="warning-list">${r.warnings.map(w=>`<li>${escape(w)}</li>`).join('')}</ul></details><details><summary>Para liberar descontos e líquido reais</summary><ul>${r.pending.map(w=>`<li>${escape(w)}</li>`).join('')}</ul></details></div>`;
  $$('.export').forEach(b=>b.addEventListener('click',()=>exportResult(b.dataset.format)));
}

async function loadRealCatalog() {
  const data=await api('/api/career-data');
  const panel=document.createElement('div');panel.className='panel real-catalog';
  const families=['DAD','DAI','FGD','FGI','GTED','GTEI'];
  panel.innerHTML=`<h2>Tabelas reais da carreira · 2026</h2><p>50 posições, 52 cargos e 45 funções/gratificações, com cópias das fontes e hashes preservados. Conferência em ${escape(data.verified_at)}. Descontos não certificados.</p><details><summary>Vencimento básico e pontuação GDPI · todas as posições</summary><div class="table-scroll"><table><thead><tr><th>POSIÇÃO</th><th>VB</th><th>PONTOS TABELA</th><th>PONTOS VARIÁVEIS · 50%</th></tr></thead><tbody>${data.positions.map(p=>`<tr><td>${escape(p.level)}-${escape(p.grade)}</td><td>${currency(p.salary)}</td><td>${number(p.points)}</td><td>${number(Number(p.points)*Number(data.gdpi_point_share))}</td></tr>`).join('')}</tbody></table></div></details>${families.map(family=>{const rows=[...data.commissions,...data.functions].filter(v=>v.kind===family);return `<details><summary>${family} · ${rows.length} níveis</summary><div class="table-scroll"><table><thead><tr><th>CARGO / FUNÇÃO</th><th>VALOR INTEGRAL</th></tr></thead><tbody>${rows.map(v=>`<tr><td>${escape(v.code)}</td><td>${currency(v.amount)}</td></tr>`).join('')}</tbody></table></div></details>`;}).join('')}<details><summary>Documentos oficiais consultados e integridade</summary><ul class="document-list">${data.evidence.map(e=>`<li>${/^https:\/\/www\.(mg|almg)\.gov\.br\//.test(e.url)?`<a href="${escape(e.url)}" target="_blank" rel="noopener noreferrer">${escape(e.component)} · fonte oficial ↗</a>`:escape(e.component)}<br><code class="code">SHA-256 ${escape(e.sha256)}</code></li>`).join('')}</ul></details>`;
  $('#sources-content').append(panel);
}
