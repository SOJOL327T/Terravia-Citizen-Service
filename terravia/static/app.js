(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const readCookie = name => document.cookie.split('; ').find(v => v.startsWith(`${name}=`))?.slice(name.length + 1) || '';
  const notice = (message, type = '') => {
    const node = $('#notice'); node.textContent = message; node.className = `notice${type ? ` ${type}` : ''}`;
    node.classList.remove('hidden'); window.scrollTo({top: 0, behavior: 'smooth'});
    clearTimeout(notice.timer); notice.timer = setTimeout(() => node.classList.add('hidden'), 7000);
  };
  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body) headers.set('Content-Type', 'application/json');
    if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', decodeURIComponent(readCookie('tv_csrf')));
    const response = await fetch(path, {...options, headers, credentials: 'same-origin'});
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.error?.message || data?.detail || `Request failed (${response.status})`);
    return data;
  }
  const esc = value => String(value ?? '');
  const element = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const record = (title, description, badgeText = '', badgeClass = '') => {
    const n = element('div', 'record'), top = element('div', 'record-top');
    top.append(element('strong', '', title)); if (badgeText) top.append(element('span', `badge ${badgeClass}`, badgeText));
    n.append(top); if (description) n.append(element('p', '', description)); return n;
  };
  const list = (selector, rows, make, emptyText) => {
    const target = $(selector); target.replaceChildren();
    if (!rows?.length) { target.append(element('div', 'empty', emptyText)); return; }
    rows.forEach(row => target.append(make(row)));
  };
  const formValues = form => Object.fromEntries(new FormData(form).entries());
  const showAuth = () => { $('#workspace').classList.add('hidden'); $('#welcome').classList.remove('hidden'); $('#signout').classList.add('hidden'); $('#auth-status').textContent = 'Private by default'; };
  const showWorkspace = async () => {
    const me = await api('/v1/me');
    $('#welcome').classList.add('hidden'); $('#workspace').classList.remove('hidden'); $('#signout').classList.remove('hidden');
    $('#auth-status').textContent = me.person_id.slice(0, 8) + '…'; $('#greeting').textContent = 'Your private workspace';
    await refresh();
  };
  let serviceCache = [];
  async function refresh() {
    try {
      const [me, person, conflicts, services, requests, transfers, applications, networks, events, vault, auditEvents, control] = await Promise.all([
        api('/v1/me'), api(`/v1/persons/${encodeURIComponent((await api('/v1/me')).person_id)}`), api('/v1/conflicts'), api('/v1/services'),
        api('/v1/data-requests'), api('/v1/transfers'), api('/v1/applications'), api('/v1/family/networks'),
        api('/v1/life-events'), api('/v1/legacy/vault'), api('/v1/audit'), api('/v1/controls/automation')
      ]);
      $('#claim-count').textContent = person.claims.length; $('#credential-count').textContent = person.credentials.length;
      $('#review-count').textContent = conflicts.filter(c => c.state !== 'RESOLVED').length + requests.filter(r => r.status === 'AWAITING_CITIZEN_REVIEW').length;
      $('#transfer-count').textContent = transfers.length;
      $('#control-state').textContent = control.state; $('#control-state').className = `state-pill ${control.state.toLowerCase()}`;
      $('#claims-subcount').textContent = person.claims.length ? `(${person.claims.length})` : '';
      list('#claims-list', person.claims, c => record(c.attribute, `${esc(c.value)} · ${c.source_type}${c.source_reference ? ` · ${c.source_reference}` : ''}`, c.verification_status, 'review'), 'No claims yet.');
      $('#credentials-subcount').textContent = person.credentials.length ? `(${person.credentials.length})` : '';
      list('#credentials-list', person.credentials, c => record(c.type, `${c.issuer}${c.external_identifier ? ` · Ref ${c.external_identifier}` : ''}`, c.verification_status, 'review'), 'No credentials linked yet.');
      list('#conflicts-list', conflicts, c => { const n = record(c.attribute, `${c.claim_ids.length} different claim values · Claims are preserved for review.`, c.state, 'review'); if (c.state === 'OPEN' || c.state === 'DISPUTED') { const b=element('button','secondary','Request review'); b.type='button'; b.addEventListener('click',()=>action(`/v1/conflicts/${c.id}/review`, 'POST', {}).then(refresh)); n.append(b); } return n; }, 'No identity conflicts.');
      list('#services-list', services, s => { const n=record(s.name, `${s.description} · Required: ${s.required_fields.join(', ')}`, s.adapter_mode, 'mock'); const b=element('button','secondary','Check readiness'); b.type='button'; b.addEventListener('click',()=>action(`/v1/applications?service_id=${encodeURIComponent(s.id)}`,'POST',{})); n.append(b); return n; }, 'No services available.');
      serviceCache=services;
      const select=$('#request-service'); select.replaceChildren(); services.forEach(s=>{const o=element('option','',`${s.name} · ${s.adapter_mode}`);o.value=s.id;o.dataset.organization=s.organization;select.append(o);});
      list('#requests-list', requests, r => {
        const fields=r.requested_fields || []; const activeScope=r.active_consent?.scope||[]; const n=record(`${r.requester} · ${r.status}`, `${r.purpose} · Requested: ${fields.join(', ')}${activeScope.length?` · Consented: ${activeScope.join(', ')}`:''} · Expires ${r.expires_at} · Policy ${r.policy_outcome}: ${r.policy_reason}`, r.policy_outcome, r.policy_outcome==='DENY'?'review':'');
        if (r.status==='AWAITING_CITIZEN_REVIEW' || r.status==='CONSENT_GRANTED') {
          const buttons=element('div','button-row');
          if (r.status==='AWAITING_CITIZEN_REVIEW') { const grant=element('button','secondary','Choose consent fields'); grant.type='button'; grant.addEventListener('click',async()=>{const chosen=prompt(`Review the requester and purpose above. Type only fields you agree to share, separated by commas:\n${fields.join(', ')}`); if(chosen===null)return; const selected=chosen.split(',').map(x=>x.trim()).filter(Boolean); await action(`/v1/data-requests/${r.id}/consents`,'POST',{fields:selected}); await refresh();}); buttons.append(grant); }
          if (r.status==='CONSENT_GRANTED') { const consent=awaitConsent(r.id); const send=element('button','secondary','Send through mock adapter'); send.type='button'; send.addEventListener('click',async()=>{if(!confirm('This will send only the consented fields to the clearly labeled mock service. Continue?'))return; await action(`/v1/transfers?request_id=${encodeURIComponent(r.id)}&consent_id=${encodeURIComponent(consent?.id||'')}`,'POST',{}, {'Idempotency-Key': crypto.randomUUID()}); await refresh();}); buttons.append(send); }
          n.append(buttons);
        }
        if (r.active_consent?.id) { const revoke=element('button','quiet','Revoke consent'); revoke.type='button'; revoke.addEventListener('click',()=>{if(confirm('Stop future transfers under this consent?'))actionThen(`/v1/consents/${r.active_consent.id}/revoke`,'POST',{},refresh);}); n.append(revoke); }
        if(r.status==='DENIED') n.querySelector('.badge')?.classList.add('review'); return n;
      }, 'No data requests.');
      list('#transfers-list', transfers, t => record(`${t.receipt.recipient} · ${t.adapter_mode}`, `${t.receipt.fields.join(', ')} · ${t.receipt.transferred_at}`, t.receipt.status, 'mock'), 'No transfers have been made.');
      list('#applications-list', applications, a => record(a.service_name, `${a.readiness.status} · Missing: ${a.readiness.missing_fields.join(', ')||'none'}${a.readiness.conflicted_fields.length?` · Conflicts: ${a.readiness.conflicted_fields.join(', ')}`:''}`, a.adapter_mode, 'mock'), 'No applications prepared.');
      fillNetworkSelects(networks);
      list('#networks-list', networks, n => record(n.name, `Private · Created ${n.created_at}`, 'PRIVATE', 'private'), 'No family networks yet.');
      const familyItems=[]; for(const n of networks){ const [relationships,items]=await Promise.all([api(`/v1/family/networks/${n.id}/relationships`),api(`/v1/family/networks/${n.id}/items`)]); relationships.forEach(x=>familyItems.push({...x,title:`${x.related_label} · ${x.relationship_type}`,item_type:'Relationship'})); items.forEach(x=>familyItems.push(x)); }
      list('#family-items-list', familyItems, x=>record(x.title, `${x.item_type||'Relationship'} · ${x.evidence_level||''} · ${x.certainty||x.state||''}`, x.visibility||'FAMILY','private'), 'No family notes yet.');
      list('#life-events-list', events, e=>record(e.event_type, `${e.state} · ${e.risk} risk · Suggested review only: ${(e.impact_analysis||[]).map(i=>i.domain).join(', ')||'no domains'} · No records changed automatically.`,e.state,'review'), 'No life events proposed.');
      $('#vault-view').replaceChildren();
      if(vault.status==='NOT_CREATED') $('#vault-view').append(element('div','empty','Create a vault to begin.'));
      else { $('#vault-view').append(element('p','muted',`${vault.status} · Releases require explicit authorized trigger review.`)); list('#vault-view', vault.items, i=>record(i.title,`${i.classification} · ${i.release_mode} · Trigger ${i.trigger_type}`,i.released_at?'RELEASED':'PRIVATE','private'),'No legacy items yet.'); }
      list('#audit-list', auditEvents, e=>record(e.action,`${e.timestamp} · ${e.object_type}${e.purpose?` · ${e.purpose}`:''}`,e.result,''),'No activity yet.');
    } catch (err) { notice(err.message, 'error'); }
  }
  async function awaitConsent(requestId) {
    const rows = await api('/v1/data-requests'); const r=rows.find(x=>x.id===requestId); if(!r)return null;
    return r.active_consent ? {id:r.active_consent.id} : null;
  }
  function fillNetworkSelects(networks){ ['#relationship-network','#item-network'].forEach(sel=>{const node=$(sel);node.replaceChildren();networks.forEach(n=>{const o=element('option','',n.name);o.value=n.id;node.append(o);});}); }
  async function action(path, method='POST', body={}, headers={}) { try { const result=await api(path,{method,body:JSON.stringify(body),headers}); notice(result?.id?`Saved. Record ${result.id.slice(0,8)}…`:'Action completed.'); return result; } catch(err){ notice(err.message,'error'); return null; } }
  async function actionThen(path, method, body, done){const result=await action(path,method,body);if(result)await done(result);}

  let authMode='signin';
  $$('.auth-tab').forEach(b=>b.addEventListener('click',()=>{authMode=b.dataset.auth;$$('.auth-tab').forEach(x=>x.classList.toggle('active',x===b));$('#auth-submit').firstChild.textContent=authMode==='create'?'Create TerraVia ID ':'Sign in securely ';$('#password-hint').textContent=authMode==='create'?'Use at least 12 characters.':'Use your account password.';}));
  $('#auth-form').addEventListener('submit',async e=>{e.preventDefault();const body=formValues(e.currentTarget);try{await api(authMode==='create'?'/v1/auth/register':'/v1/auth/login',{method:'POST',body:JSON.stringify(body)});await showWorkspace();}catch(err){notice(err.message,'error');}});
  $('#signout').addEventListener('click',async()=>{try{await api('/v1/auth/logout',{method:'POST',body:'{}'});}catch{}showAuth();});
  $('#refresh').addEventListener('click',refresh);
  $$('.section-nav button').forEach(b=>b.addEventListener('click',()=>{ $$('.section-nav button').forEach(x=>x.classList.toggle('selected',x===b)); $$('.panel').forEach(x=>x.classList.toggle('active',x.id===b.dataset.section)); }));
  $$('[data-jump]').forEach(b=>b.addEventListener('click',()=>{const section=b.dataset.jump;$$('.section-nav button').find(x=>x.dataset.section===section)?.click();}));
  $('#claim-form').addEventListener('submit',e=>{e.preventDefault();const v=formValues(e.currentTarget);const value=v.value;actionThen('/v1/claims','POST',{...v,value},refresh);e.currentTarget.reset();});
  $('#credential-form').addEventListener('submit',e=>{e.preventDefault();actionThen('/v1/credentials','POST',formValues(e.currentTarget),refresh);e.currentTarget.reset();});
  $('#request-form').addEventListener('submit',e=>{e.preventDefault();const v=formValues(e.currentTarget);const fields=[...e.currentTarget.elements.requested_fields.selectedOptions].map(o=>o.value);const requester=$('#request-service').selectedOptions[0]?.dataset.organization||'';actionThen('/v1/data-requests','POST',{...v,requester,requested_fields:fields,legal_basis:'CONSENT'},refresh);});
  $('#network-form').addEventListener('submit',e=>{e.preventDefault();actionThen('/v1/family/networks','POST',formValues(e.currentTarget),refresh);e.currentTarget.reset();});
  $('#relationship-form').addEventListener('submit',e=>{e.preventDefault();const v=formValues(e.currentTarget);const id=v.network_id;delete v.network_id;actionThen(`/v1/family/networks/${id}/relationships`,'POST',v,refresh);e.currentTarget.reset();});
  $('#family-item-form').addEventListener('submit',e=>{e.preventDefault();const v=formValues(e.currentTarget);const id=v.network_id;delete v.network_id;actionThen(`/v1/family/networks/${id}/items`,'POST',v,refresh);e.currentTarget.reset();});
  $('#life-form').addEventListener('submit',e=>{e.preventDefault();const v=formValues(e.currentTarget);v.affected_domains=(v.affected_domains||'').split(',').map(x=>x.trim()).filter(Boolean);v.evidence_references=[];actionThen('/v1/life-events','POST',v,refresh);e.currentTarget.reset();});
  $('#create-vault').addEventListener('click',()=>actionThen('/v1/legacy/vault','POST',{},refresh));
  $('#legacy-form').addEventListener('submit',e=>{e.preventDefault();actionThen('/v1/legacy/items','POST',formValues(e.currentTarget),refresh);e.currentTarget.reset();});
  $('#stop-control').addEventListener('click',async()=>{if(confirm('Stop all outbound transfers across TerraVia?'))await actionThen('/v1/controls/automation/stop','POST',{},refresh);});
  $('#resume-control').addEventListener('click',async()=>{const control_key=prompt('Enter the platform control key. It is never stored in the browser.');if(!control_key)return;try{await api('/v1/controls/automation/resume',{method:'POST',body:'{}',headers:{'X-Control-Key':control_key}});notice('Outbound transfers resumed.');await refresh();}catch(err){notice(err.message,'error');}});
  $('#explain').addEventListener('click',async()=>{const target=$('#assistant-result');target.classList.remove('hidden');target.textContent='Contacting configured local Ollama…';try{const r=await api('/v1/assistant/explain',{method:'POST',body:'{}'});target.replaceChildren(element('strong','','Suggested explanation · Ollama'));target.append(element('p','',r.text));}catch(err){target.textContent=err.message;}});
  api('/v1/me').then(showWorkspace).catch(showAuth);
})();
