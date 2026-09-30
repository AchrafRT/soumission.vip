from pathlib import Path
import os, time, uuid, secrets, json, threading, math
from storage import Store, APP_ROOT
from security import hash_password, verify_password
from sessions import SessionStore
from patch_engine import process_patches
from export_engine import extract_all
from payments import stripe_checkout, paypal_checkout

ALL_TABS=['dashboard','tree','branding','businesses','clients','jobs','invites','employees','growth','monetization','maintenance']

class DirectoryAPI:
    def __init__(self):
        self.store=Store(); self.sessions=SessionStore(self.store); self._api_lock=threading.RLock(); self._ensure_demo()
    def _now(self): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    def _id(self,prefix): return prefix+'_'+uuid.uuid4().hex[:12]
    def _ensure_demo(self):
        # Demo accounts are opt-in in hardened builds; never seed default credentials in production.
        if os.environ.get('ENABLE_DEMO','0')!='1': return
        users=self.store.load('users.json',[]) or []
        changed=False
        if not any(u.get('username','').lower()=='demo' for u in users):
            users.append({'id':'user_demo','username':'demo','password_hash':hash_password('admin'),'role':'demo','permissions':ALL_TABS,'active':True,'created_at':self._now()}); changed=True
        role_demos=[('user_client_demo','Client','client'),('user_business_demo','Business','business')]
        for uid,username,role in role_demos:
            if not any(u.get('username','').lower()==username.lower() for u in users):
                users.append({'id':uid,'username':username,'password_hash':hash_password('admin'),'role':role,'permissions':[],'active':True,'created_at':self._now()}); changed=True
        if changed: self.store.save('users.json',users)
        clients=self.store.load('homeowners.json',[]) or []
        if not any(x.get('user_id')=='user_client_demo' for x in clients):
            clients.append({'id':'client_demo','user_id':'user_client_demo','name':'Client Demo','email':'','phone':'','city':'Toronto','private':True,'created_at':self._now()}); self.store.save('homeowners.json',clients)
        businesses=self.store.load('businesses.json',[]) or []
        if not any(x.get('user_id')=='user_business_demo' for x in businesses):
            businesses.append({'id':'biz_demo','user_id':'user_business_demo','name':'Business Demo','tagline':'Local pros. Clear scope. Fast response.','email':'hello@business-demo.local','phone':'','city':'Toronto','category':'General Services','description':'A demonstration company profile showing the marketplace listing experience. Replace every demo field with your real company information before publishing.','website':'','service_area':'Toronto & GTA','specialties':['Repairs','Renovations','Emergency help'],'years_in_business':'10+','license_info':'Add licences or trade credentials here when applicable.','insurance_info':'Add insurance details here when applicable.','hours':'Mon–Fri 8:00–17:00','social_links':{},'custom_links':[],'logo_data_url':'','banner_data_url':'','gallery':[],'active':True,'created_at':self._now()}); self.store.save('businesses.json',businesses)
    def _owner_exists(self): return any(u.get('role')=='owner' for u in (self.store.load('users.json',[]) or []))
    def _user(self,token):
        ses=self.sessions.get(token)
        if not ses or ses.get('kind')!='user': return None
        return next((u for u in (self.store.load('users.json',[]) or []) if u.get('id')==ses.get('user_id') and u.get('active',True)),None)
    def _require(self,token,tab=None, roles=None):
        u=self._user(token)
        if not u: raise PermissionError('Login required.')
        role=u.get('role')
        if roles and role not in roles: raise PermissionError('This account cannot perform that action.')
        # Admin tabs are never implicitly available to customer/business portal roles.
        if tab:
            if role=='owner':
                pass
            elif role=='employee':
                if tab not in u.get('permissions',[]): raise PermissionError('No access to this tab.')
            elif role=='demo':
                if tab not in ['dashboard','tree','branding','businesses','clients','jobs','invites','employees','monetization']:
                    raise PermissionError('No access to this tab.')
            else:
                raise PermissionError('Administrative access required.')
        return u
    def _deny_demo_write(self,u):
        if u.get('role')=='demo': raise PermissionError('Demo account is read-only.')
    def call(self, method, payload=None, token=None):
        payload=payload or {}
        fn=getattr(self,'api_'+method,None)
        if not fn or method.startswith('_'): return {'ok':False,'error':'Unknown API method.'}
        try:
            # Serialize API commands so each read/validate/modify/write sequence is atomic
            # inside this deployment. This prevents lost updates under ThreadingHTTPServer.
            with self._api_lock:
                data=fn(payload,token)
            return {'ok':True,'data':data}
        except Exception as e:
            return {'ok':False,'error':str(e)}

    def api_bootstrap(self,p,t):
        cfg=self.store.load('config.json',{}) or {}
        return {'owner_exists':self._owner_exists(),'onboarding_complete':cfg.get('onboarding_complete',False),'branding':{k:cfg.get(k,'') for k in ['directory_name','slogan','logo_data_url','currency','country']},'public':self._public_payload(),'version':cfg.get('version','1.0.0')}
    def api_dev_unlock(self,p,t):
        expected=os.environ.get('DEV_PASSWORD','').strip()
        if not expected: raise PermissionError('Developer setup is disabled until DEV_PASSWORD is configured.')
        if not secrets.compare_digest(str(p.get('password','')),expected): raise PermissionError('Invalid developer password.')
        return {'setup_token':self.sessions.create('__setup__','setup',2)}
    def api_create_owner(self,p,t):
        ses=self.sessions.get(p.get('setup_token'))
        if not ses or ses.get('kind')!='setup': raise PermissionError('Developer setup access required.')
        if self._owner_exists(): raise RuntimeError('Owner account already exists.')
        username=str(p.get('username','')).strip(); password=str(p.get('password',''))
        if len(username)<3 or len(password)<6: raise ValueError('Username must be 3+ characters and password 6+ characters.')
        users=self.store.load('users.json',[]) or []
        if any(u.get('username','').lower()==username.lower() for u in users): raise ValueError('Username already exists.')
        uid=self._id('user'); users.append({'id':uid,'username':username,'password_hash':hash_password(password),'role':'owner','permissions':ALL_TABS,'active':True,'created_at':self._now()}); self.store.save('users.json',users)
        cfg=self.store.load('config.json',{}); cfg['onboarding_stage']=3; cfg['created_at']=cfg.get('created_at') or self._now(); self.store.save('config.json',cfg)
        return {'token':self.sessions.create(uid),'user':{'id':uid,'username':username,'role':'owner','permissions':ALL_TABS}}
    def api_login(self,p,t):
        username=str(p.get('username','')).strip().lower(); password=str(p.get('password',''))
        u=next((u for u in (self.store.load('users.json',[]) or []) if u.get('username','').lower()==username and u.get('active',True)),None)
        if not u or not verify_password(password,u.get('password_hash','')): raise PermissionError('Invalid username or password.')
        return {'token':self.sessions.create(u['id']),'user':{k:u.get(k) for k in ['id','username','role','permissions']}}
    def api_logout(self,p,t): self.sessions.delete(t); return {'logged_out':True}
    def api_session_state(self,p,t):
        u=self._user(t)
        if not u: raise PermissionError('Login required.')
        return {'user':{k:u.get(k) for k in ['id','username','role','permissions']}}
    def api_admin_state(self,p,t):
        u=self._require(t,roles=['owner','employee','demo'])
        cfg=self.store.load('config.json',{}) or {}
        businesses=self.store.load('businesses.json',[]) or []; clients=self.store.load('homeowners.json',[]) or []; jobs=self.store.load('jobs.json',[]) or []; quotes=self.store.load('quotes.json',[]) or []
        users=self.store.load('users.json',[]) or []
        employees=[{k:x.get(k) for k in ['id','username','role','permissions','active','created_at']} for x in users if x.get('role')=='employee']
        leads=self.store.load('leads.json',[]) or []; analytics=self.store.load('analytics.json',{}) or {}
        metrics={'businesses':len(businesses),'clients':len(clients),'jobs':len(jobs),'quotes':len(quotes),'employees':len(employees),'leads':len(leads),'page_views':int(analytics.get('page_views',0) or 0),'events':int(analytics.get('events',0) or 0)}
        if u.get('role')=='demo':
            safe_cfg={k:cfg.get(k) for k in ['directory_name','slogan','logo_data_url','public_base_url','country','currency','onboarding_complete','onboarding_stage','version','brand_theme','default_language','enabled_languages']}
            safe_cfg['monetization']=cfg.get('monetization',{})
            safe_cfg['growth']=cfg.get('growth',{})
            safe_businesses=[{k:x.get(k) for k in ['id','name','category','city','description','active','created_at']} for x in businesses]
            safe_jobs=[{k:x.get(k) for k in ['id','title','category','city','timing','description','status','direct_business_id','created_at']} for x in jobs]
            return {'user':{k:u.get(k) for k in ['id','username','role','permissions']},'config':safe_cfg,'tree':self.store.load('service_tree.json',{}),'locations':self.store.load('locations.json',{}),'businesses':safe_businesses,'clients':[{'id':'demo-client','name':'Demo Homeowner','city':'Toronto'}],'jobs':safe_jobs,'quotes':[],'invites':[],'employees':[],'leads':[],'analytics':analytics,'metrics':metrics}
        perms=set(u.get('permissions',[])) if u.get('role')=='employee' else set(ALL_TABS)
        filtered_cfg={k:cfg.get(k) for k in ['directory_name','slogan','logo_data_url','public_base_url','country','currency','onboarding_complete','onboarding_stage','version','brand_theme','default_language','enabled_languages']}
        if 'monetization' in perms: filtered_cfg['monetization']=cfg.get('monetization',{})
        else: filtered_cfg['monetization']={}
        if 'growth' in perms: filtered_cfg['growth']=cfg.get('growth',{})
        else: filtered_cfg['growth']={}
        return {
            'user':{k:u.get(k) for k in ['id','username','role','permissions']},
            'config':filtered_cfg,
            'tree':self.store.load('service_tree.json',{}) if ('tree' in perms or 'dashboard' in perms) else {},
            'locations':self.store.load('locations.json',{}) if ('tree' in perms or 'dashboard' in perms) else {},
            'businesses':businesses if 'businesses' in perms else [],
            'clients':clients if 'clients' in perms else [],
            'jobs':jobs if 'jobs' in perms else [],
            'quotes':quotes if 'jobs' in perms else [],
            'invites':self.store.load('invites.json',[]) or [] if 'invites' in perms else [],
            'employees':employees if 'employees' in perms else [],
            'leads':leads if 'growth' in perms else [],
            'analytics':analytics if ('growth' in perms or 'dashboard' in perms) else {},
            'metrics':metrics
        }
    def api_portal_state(self,p,t):
        u=self._require(t,roles=['client','business'])
        public=self._public_payload(); jobs=self.store.load('jobs.json',[]) or []; quotes=self.store.load('quotes.json',[]) or []
        if u.get('role')=='client':
            profile=next((x for x in (self.store.load('homeowners.json',[]) or []) if x.get('user_id')==u['id']),{})
            mine=[x for x in jobs if x.get('created_by_user_id')==u['id']]
            ids={x.get('id') for x in mine}; my_quotes=[q for q in quotes if q.get('job_id') in ids]
            return {'user':{k:u.get(k) for k in ['id','username','role']},'profile':profile,'my_jobs':mine,'quotes':my_quotes,'public':public}
        profile=next((x for x in (self.store.load('businesses.json',[]) or []) if x.get('user_id')==u['id']),{})
        mine=[q for q in quotes if q.get('created_by_user_id')==u['id']]
        visible_jobs=[x for x in jobs if x.get('status','open')=='open' and (not x.get('direct_business_id') or x.get('direct_business_id')==profile.get('id'))]
        return {'user':{k:u.get(k) for k in ['id','username','role']},'profile':profile,'open_jobs':visible_jobs,'my_quotes':mine,'public':public}
    def api_save_tree(self,p,t):
        u=self._require(t,'tree',roles=['owner','employee']); self._deny_demo_write(u)
        tree=p.get('tree');
        if not isinstance(tree,dict): raise ValueError('Invalid service tree.')
        self.store.save('service_tree.json',tree); self.store.append_runtime('audit.txt',{'at':self._now(),'user':u['username'],'action':'save_tree'}); return {'saved':True}
    def api_save_branding(self,p,t):
        u=self._require(t,'branding',roles=['owner','employee']); self._deny_demo_write(u)
        cfg=self.store.load('config.json',{})
        for k in ['directory_name','slogan','logo_data_url','public_base_url','country','currency','brand_theme','default_language','enabled_languages']:
            if k in p: cfg[k]=p[k]
        if cfg.get('default_language') not in ['en','fr']: cfg['default_language']='en'
        langs=cfg.get('enabled_languages') or ['en','fr']; cfg['enabled_languages']=[x for x in langs if x in ['en','fr']] or ['en','fr']
        cfg['onboarding_stage']=max(int(cfg.get('onboarding_stage',1)),4); self.store.save('config.json',cfg); return cfg
    def api_finish_onboarding(self,p,t):
        u=self._require(t,roles=['owner']); self._deny_demo_write(u)
        cfg=self.store.load('config.json',{}); cfg['onboarding_complete']=True; cfg['onboarding_stage']=5; self.store.save('config.json',cfg); return {'complete':True}
    def api_create_employee(self,p,t):
        u=self._require(t,'employees',roles=['owner']); self._deny_demo_write(u)
        username=str(p.get('username','')).strip(); password=str(p.get('password','')); perms=[x for x in p.get('permissions',[]) if x in ALL_TABS]
        if len(username)<3 or len(password)<6: raise ValueError('Employee username 3+ chars; password 6+ chars.')
        users=self.store.load('users.json',[]) or []
        if any(x.get('username','').lower()==username.lower() for x in users): raise ValueError('Username already exists.')
        uid=self._id('user'); users.append({'id':uid,'username':username,'password_hash':hash_password(password),'role':'employee','permissions':perms,'active':True,'created_at':self._now()}); self.store.save('users.json',users); return {'id':uid}
    def api_remove_employee(self,p,t):
        u=self._require(t,'employees',roles=['owner']); self._deny_demo_write(u); users=self.store.load('users.json',[]) or []; users=[x for x in users if not (x.get('id')==p.get('id') and x.get('role')=='employee')]; self.store.save('users.json',users); return {'removed':True}
    def _crud_create(self,file,prefix,p,role=None):
        rows=self.store.load(file,[]) or []; item=dict(p); item['id']=self._id(prefix); item['created_at']=self._now(); rows.append(item); self.store.save(file,rows); return item
    def _crud_remove(self,file,id):
        rows=self.store.load(file,[]) or []; before=len(rows); rows=[r for r in rows if r.get('id')!=id]; self.store.save(file,rows); return before-len(rows)
    def api_create_business(self,p,t):
        u=self._require(t,'businesses',roles=['owner','employee']); self._deny_demo_write(u); return self._crud_create('businesses.json','biz',p)
    def api_remove_business(self,p,t):
        u=self._require(t,'businesses',roles=['owner','employee']); self._deny_demo_write(u); return {'removed':bool(self._crud_remove('businesses.json',p.get('id')))}
    def api_create_client(self,p,t):
        u=self._require(t,'clients',roles=['owner','employee']); self._deny_demo_write(u); return self._crud_create('homeowners.json','client',p)
    def api_remove_client(self,p,t):
        u=self._require(t,'clients',roles=['owner','employee']); self._deny_demo_write(u); return {'removed':bool(self._crud_remove('homeowners.json',p.get('id')))}
    def api_create_invite(self,p,t):
        u=self._require(t,'invites',roles=['owner','employee']); self._deny_demo_write(u); typ=p.get('type')
        if typ not in ['business','client']: raise ValueError('Invite type must be business or client.')
        token=secrets.token_urlsafe(24); cfg=self.store.load('config.json',{}) or {}; base=(os.environ.get('PUBLIC_BASE_URL') or os.environ.get('RENDER_EXTERNAL_URL') or cfg.get('public_base_url') or p.get('base_url') or 'http://127.0.0.1:8765').rstrip('/')
        item=self._crud_create('invites.json','invite',{'name':p.get('name',''),'type':typ,'token':token,'status':'pending','url':f'{base}/invite?token={token}'})
        return item
    def api_public_signup(self,p,t):
        cfg=self.store.load('config.json',{}) or {}; invite_token=p.get('invite_token',''); role=p.get('role')
        invite=None
        if invite_token: invite=next((x for x in (self.store.load('invites.json',[]) or []) if x.get('token')==invite_token and x.get('status')=='pending'),None); role=invite.get('type') if invite else None
        if role not in ['business','client'] or (not invite and not cfg.get('allow_public_signup',True)): raise PermissionError('Public signup is disabled or invite invalid.')
        username=str(p.get('username','')).strip(); password=str(p.get('password',''))
        if len(username)<3 or len(password)<6: raise ValueError('Username 3+ chars; password 6+ chars.')
        users=self.store.load('users.json',[]) or []
        if any(x.get('username','').lower()==username.lower() for x in users): raise ValueError('Username already exists.')
        uid=self._id('user'); users.append({'id':uid,'username':username,'password_hash':hash_password(password),'role':role,'permissions':[],'active':True,'created_at':self._now()}); self.store.save('users.json',users)
        profile={'user_id':uid,'name':p.get('name') or username,'email':p.get('email',''),'phone':p.get('phone',''),'city':p.get('city','')}
        if role=='business': profile=self._crud_create('businesses.json','biz',profile)
        else: profile=self._crud_create('homeowners.json','client',profile)
        if invite:
            rows=self.store.load('invites.json',[]); [x.update({'status':'used','used_at':self._now(),'user_id':uid}) for x in rows if x.get('id')==invite.get('id')]; self.store.save('invites.json',rows)
        return {'token':self.sessions.create(uid),'role':role,'profile':profile}
    def api_update_portal_profile(self,p,t):
        u=self._require(t,roles=['client','business'])
        file='homeowners.json' if u.get('role')=='client' else 'businesses.json'
        allowed=['name','email','phone','city'] if u.get('role')=='client' else ['name','email','phone','city','category','description','website','active','tagline','service_area','specialties','years_in_business','license_info','insurance_info','hours','social_links','custom_links','logo_data_url','banner_data_url','gallery']
        rows=self.store.load(file,[]) or []; found=None
        for row in rows:
            if row.get('user_id')==u['id']:
                for k in allowed:
                    if k in p: row[k]=p[k]
                row['updated_at']=self._now(); found=row; break
        if found is None: raise RuntimeError('Profile not found.')
        self.store.save(file,rows); return found
    def api_create_job(self,p,t):
        u=self._require(t); self._deny_demo_write(u)
        if u.get('role') not in ['owner','client','employee']: raise PermissionError('Only clients or staff can create jobs.')
        if u.get('role')=='employee' and 'jobs' not in u.get('permissions',[]): raise PermissionError('No access to this tab.')
        item=dict(p); item['created_by_user_id']=u['id']; item.setdefault('status','open')
        if u.get('role')=='client':
            prof=next((x for x in (self.store.load('homeowners.json',[]) or []) if x.get('user_id')==u['id']),{})
            item['client_id']=prof.get('id'); item['client_name']=prof.get('name',u.get('username'))
        return self._crud_create('jobs.json','job',item)
    def api_remove_job(self,p,t):
        u=self._require(t); self._deny_demo_write(u)
        job_id=p.get('id'); rows=self.store.load('jobs.json',[]) or []
        job=next((x for x in rows if x.get('id')==job_id),None)
        if not job: return {'removed':False}
        if u.get('role')=='client' and job.get('created_by_user_id')!=u.get('id'):
            raise PermissionError('Clients may only remove their own jobs.')
        if u.get('role')=='employee' and 'jobs' not in u.get('permissions',[]): raise PermissionError('No access to this tab.')
        if u.get('role') not in ['owner','employee','client']: raise PermissionError('This account cannot remove jobs.')
        return {'removed':bool(self._crud_remove('jobs.json',job_id))}
    def api_create_quote(self,p,t):
        u=self._require(t); self._deny_demo_write(u)
        if u.get('role') not in ['business','owner','employee']: raise PermissionError('Only businesses or staff can submit quotes.')
        if u.get('role')=='employee' and 'jobs' not in u.get('permissions',[]): raise PermissionError('No access to this tab.')
        job_id=str(p.get('job_id','')).strip()
        job=next((x for x in (self.store.load('jobs.json',[]) or []) if x.get('id')==job_id),None)
        if not job: raise ValueError('Job does not exist.')
        if job.get('status','open')!='open': raise ValueError('Job is not open for quotes.')
        amount=p.get('amount',p.get('amount_cents'))
        if amount is not None:
            try: numeric=float(amount)
            except Exception: raise ValueError('Quote amount must be numeric.')
            if not math.isfinite(numeric) or numeric < 0: raise ValueError('Quote amount must be finite and non-negative.')
        item={k:v for k,v in dict(p).items() if k not in ['created_by_user_id','business_id','business_name','created_at','id','status']}; item['created_by_user_id']=u['id']; item['status']='submitted'
        if u.get('role')=='business':
            prof=next((x for x in (self.store.load('businesses.json',[]) or []) if x.get('user_id')==u['id']),{})
            item['business_id']=prof.get('id'); item['business_name']=prof.get('name',u.get('username'))
        return self._crud_create('quotes.json','quote',item)

    def api_save_growth(self,p,t):
        u=self._require(t,'growth',roles=['owner']); self._deny_demo_write(u)
        cfg=self.store.load('config.json',{}) or {}
        growth=p.get('growth')
        if not isinstance(growth,dict): raise ValueError('Invalid growth configuration.')
        cfg['growth']=growth; self.store.save('config.json',cfg)
        return growth
    def api_capture_lead(self,p,t):
        name=str(p.get('name','')).strip()[:120]; email=str(p.get('email','')).strip().lower()[:240]
        if '@' not in email or '.' not in email.split('@')[-1]: raise ValueError('Enter a valid email address.')
        rows=self.store.load('leads.json',[]) or []
        existing=next((x for x in rows if str(x.get('email','')).lower()==email),None)
        payload={'name':name,'email':email,'source':str(p.get('source','lead_magnet'))[:80],'lead_magnet':str(p.get('lead_magnet','Project Quote Checklist'))[:160],'city':str(p.get('city',''))[:120],'updated_at':self._now()}
        if existing: existing.update(payload); item=existing
        else:
            payload['id']=self._id('lead'); payload['created_at']=self._now(); rows.append(payload); item=payload
        self.store.save('leads.json',rows)
        self._track('lead_capture',{'source':payload['source']})
        return {'captured':True,'id':item.get('id')}
    def api_track_event(self,p,t):
        event=str(p.get('event','')).strip().lower()[:80]
        allowed={'page_view','hero_cta','search','signup_open','lead_magnet_open','lead_capture','direct_quote_start','job_post_start','business_cta'}
        if event not in allowed: return {'tracked':False}
        self._track(event,{'surface':str(p.get('surface','public'))[:60]})
        return {'tracked':True}
    def _track(self,event,meta=None):
        a=self.store.load('analytics.json',{}) or {}
        a['events']=int(a.get('events',0) or 0)+1
        if event=='page_view': a['page_views']=int(a.get('page_views',0) or 0)+1
        b=a.setdefault('event_breakdown',{}); b[event]=int(b.get(event,0) or 0)+1
        recent=a.setdefault('recent_events',[]); recent.append({'event':event,'at':self._now(),'meta':meta or {}}); a['recent_events']=recent[-100:]
        self.store.save('analytics.json',a)
    def api_save_monetization(self,p,t):
        u=self._require(t,'monetization',roles=['owner']); self._deny_demo_write(u); cfg=self.store.load('config.json',{}); cfg['monetization']=p.get('monetization',cfg.get('monetization',{})); self.store.save('config.json',cfg); return cfg['monetization']
    def api_save_payment_secrets(self,p,t):
        u=self._require(t,'monetization',roles=['owner']); self._deny_demo_write(u); current=self.store.load_private()
        for k in ['STRIPE_SECRET_KEY','PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET']:
            if p.get(k): current[k]=p[k]
        self.store.save_private(current); return {'saved':True,'configured':{k:bool(current.get(k) or os.environ.get(k)) for k in ['STRIPE_SECRET_KEY','PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET']}}
    def api_payment_checkout(self,p,t):
        cfg=self.store.load('config.json',{}) or {}; m=cfg.get('monetization',{}); kind=p.get('kind'); provider=p.get('provider'); amount=0; label='Directory payment'
        recurring_cycle=None
        if kind=='business_listing':
            listing=m.get('business_listing',{}); amount=int(listing.get('amount_cents',0)); label='Business listing fee'; recurring_cycle=listing.get('cycle','monthly')
        elif kind=='client_job': amount=int(m.get('client_fees',{}).get('job_fee_cents',0)); label='Job listing fee'
        elif kind=='client_account': amount=int(m.get('client_fees',{}).get('account_fee_cents',0)); label='Client account fee'
        if amount<=0: raise ValueError('No payable amount configured for this item.')
        base=(os.environ.get('PUBLIC_BASE_URL') or os.environ.get('RENDER_EXTERNAL_URL') or cfg.get('public_base_url') or p.get('base_url') or 'http://127.0.0.1:8765').rstrip('/')
        currency=cfg.get('currency','CAD') or 'CAD'
        if provider=='stripe': return stripe_checkout(self.store,amount,label,base+'/?payment=success',base+'/?payment=cancel',recurring_cycle,currency)
        if provider=='paypal': return paypal_checkout(self.store,amount,label,base+'/?payment=success',base+'/?payment=cancel',m.get('payments',{}).get('paypal_mode','sandbox')=='sandbox',recurring_cycle,currency)
        raise ValueError('Unknown payment provider.')
    def api_refresh_app(self,p,t):
        u=self._require(t,'maintenance',roles=['owner']); self._deny_demo_write(u); results=process_patches(); return {'patches':results,'message':'Refresh complete. UI can reload now.'}
    def api_extract_app(self,p,t):
        u=self._require(t,'maintenance',roles=['owner']); self._deny_demo_write(u); return extract_all(self.store)
    def api_public_data(self,p,t): return self._public_payload()
    def _public_payload(self):
        cfg=self.store.load('config.json',{}) or {}
        tree=self.store.load('service_tree.json',{}) or {}
        business_keys=['id','name','category','city','description','website','phone','email','active','created_at','tagline','service_area','specialties','years_in_business','license_info','insurance_info','hours','social_links','custom_links','logo_data_url','banner_data_url','gallery']
        businesses=[{k:x.get(k) for k in business_keys} for x in (self.store.load('businesses.json',[]) or []) if x.get('active',True)]
        job_keys=['id','title','category','city','timing','description','status','created_at','budget','property_type','image_data_url']
        jobs=[{k:x.get(k) for k in job_keys} for x in (self.store.load('jobs.json',[]) or []) if x.get('status','open')=='open' and not x.get('direct_business_id')]
        return {
            'branding':{k:cfg.get(k,'') for k in ['directory_name','slogan','logo_data_url','currency','country','brand_theme','default_language','enabled_languages']},
            'tree':tree,
            'locations':self.store.load('locations.json',{}),
            'businesses':businesses,
            'jobs':jobs,
            'monetization':cfg.get('monetization',{}),
            'growth':cfg.get('growth',{}),
            'allow_public_signup':cfg.get('allow_public_signup',True)
        }
