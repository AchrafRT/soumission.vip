import os, urllib.parse, urllib.request, json, base64, uuid

CYCLE_MAP={
    'daily':('day',1,'DAY',1),
    'weekly':('week',1,'WEEK',1),
    'monthly':('month',1,'MONTH',1),
    'quarterly':('month',3,'MONTH',3),
    'annually':('year',1,'YEAR',1),
}

def _secret(store,key):
    return os.environ.get(key) or store.load_private().get(key,'')

def _json_request(url, access_token, body, request_id=None):
    req=urllib.request.Request(url,data=json.dumps(body).encode('utf-8'),method='POST')
    req.add_header('Authorization','Bearer '+access_token)
    req.add_header('Content-Type','application/json')
    req.add_header('Accept','application/json')
    if request_id: req.add_header('PayPal-Request-Id',request_id)
    req.add_header('Prefer','return=representation')
    with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())

def stripe_checkout(store, amount_cents:int, label:str, success_url:str, cancel_url:str, recurring_cycle=None, currency='CAD'):
    key=_secret(store,'STRIPE_SECRET_KEY')
    if not key: raise RuntimeError('STRIPE_SECRET_KEY is not configured.')
    fields={
      'mode':'subscription' if recurring_cycle else 'payment',
      'success_url':success_url,'cancel_url':cancel_url,
      'line_items[0][quantity]':'1',
      'line_items[0][price_data][currency]':str(currency or 'CAD').lower(),
      'line_items[0][price_data][unit_amount]':str(amount_cents),
      'line_items[0][price_data][product_data][name]':label,
    }
    if recurring_cycle:
        if recurring_cycle not in CYCLE_MAP: raise ValueError('Unsupported billing cycle.')
        interval,count,_,_=CYCLE_MAP[recurring_cycle]
        fields['line_items[0][price_data][recurring][interval]']=interval
        fields['line_items[0][price_data][recurring][interval_count]']=str(count)
    req=urllib.request.Request('https://api.stripe.com/v1/checkout/sessions',data=urllib.parse.urlencode(fields).encode(),method='POST')
    req.add_header('Authorization','Bearer '+key); req.add_header('Content-Type','application/x-www-form-urlencoded')
    with urllib.request.urlopen(req,timeout=20) as r: data=json.loads(r.read())
    return {'provider':'stripe','checkout_url':data.get('url'),'id':data.get('id'),'recurring':bool(recurring_cycle),'cycle':recurring_cycle}

def _paypal_access(cid,sec,base):
    token_req=urllib.request.Request(base+'/v1/oauth2/token',data=b'grant_type=client_credentials',method='POST')
    token_req.add_header('Authorization','Basic '+base64.b64encode(f'{cid}:{sec}'.encode()).decode()); token_req.add_header('Content-Type','application/x-www-form-urlencoded')
    with urllib.request.urlopen(token_req,timeout=20) as r: return json.loads(r.read())['access_token']

def _paypal_plan(store,base,access,amount_cents,label,cycle,currency,sandbox):
    if cycle not in CYCLE_MAP: raise ValueError('Unsupported billing cycle.')
    _,_,unit,count=CYCLE_MAP[cycle]
    private=store.load_private(); cache=private.setdefault('paypal_plan_cache',{})
    cache_key=f"{'sandbox' if sandbox else 'live'}:{currency.upper()}:{amount_cents}:{cycle}"
    if cache.get(cache_key): return cache[cache_key]
    product=_json_request(base+'/v1/catalogs/products',access,{
        'name':'DirectoryForge business listing',
        'description':label[:256],
        'type':'SERVICE',
        'category':'SOFTWARE'
    },'DF-PROD-'+uuid.uuid4().hex[:20])
    plan=_json_request(base+'/v1/billing/plans',access,{
        'product_id':product['id'],
        'name':f'{label} - {cycle}'[:127],
        'description':f'{cycle.capitalize()} recurring directory listing fee'[:127],
        'billing_cycles':[{
            'frequency':{'interval_unit':unit,'interval_count':count},
            'tenure_type':'REGULAR','sequence':1,'total_cycles':0,
            'pricing_scheme':{'fixed_price':{'value':f'{amount_cents/100:.2f}','currency_code':currency.upper()}}
        }],
        'payment_preferences':{'auto_bill_outstanding':True,'payment_failure_threshold':1}
    },'DF-PLAN-'+uuid.uuid4().hex[:20])
    cache[cache_key]=plan['id']; private['paypal_plan_cache']=cache; store.save_private(private)
    return plan['id']

def paypal_checkout(store, amount_cents:int, label:str, return_url:str, cancel_url:str, sandbox=True, recurring_cycle=None, currency='CAD'):
    cid=_secret(store,'PAYPAL_CLIENT_ID'); sec=_secret(store,'PAYPAL_CLIENT_SECRET')
    if not cid or not sec: raise RuntimeError('PayPal credentials are not configured.')
    base='https://api-m.sandbox.paypal.com' if sandbox else 'https://api-m.paypal.com'
    access=_paypal_access(cid,sec,base)
    if recurring_cycle:
        plan_id=_paypal_plan(store,base,access,amount_cents,label,recurring_cycle,currency,sandbox)
        data=_json_request(base+'/v1/billing/subscriptions',access,{
            'plan_id':plan_id,
            'application_context':{
                'brand_name':'DirectoryForge','user_action':'SUBSCRIBE_NOW',
                'return_url':return_url,'cancel_url':cancel_url
            }
        },'DF-SUB-'+uuid.uuid4().hex[:20])
        approve=next((x.get('href') for x in data.get('links',[]) if x.get('rel') in ('approve','payer-action')),None)
        return {'provider':'paypal','checkout_url':approve,'id':data.get('id'),'plan_id':plan_id,'recurring':True,'cycle':recurring_cycle}
    body={'intent':'CAPTURE','purchase_units':[{'description':label,'amount':{'currency_code':currency.upper(),'value':f'{amount_cents/100:.2f}'}}], 'application_context':{'return_url':return_url,'cancel_url':cancel_url}}
    data=_json_request(base+'/v2/checkout/orders',access,body,'DF-ORDER-'+uuid.uuid4().hex[:20])
    approve=next((x.get('href') for x in data.get('links',[]) if x.get('rel') in ('approve','payer-action')),None)
    return {'provider':'paypal','checkout_url':approve,'id':data.get('id'),'recurring':False,'cycle':None}
