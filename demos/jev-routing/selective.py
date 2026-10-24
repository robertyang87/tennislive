#!/usr/bin/env python3
"""Selective, budgeted Jev shadow evaluation. Does not dispatch or change production."""
import argparse
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import collect_oncourt_interviews as collector
import demo

MODEL = 'jev-1.13.0'


def plan(item, cfg, rules):
    """Reuse baseline outcomes; ambiguous inputs alone enter the experimental queue."""
    title = item.get('title', '')
    if not isinstance(title, str) or not title.strip():
        return 'no_content'
    sources = [s for s in cfg['sources'] if s['name'] == item.get('source')]
    if any(s.get('require_tennis') for s in sources) and not collector.is_tennis(title, rules):
        return 'existing_sport_gate'
    if item.get('id') in cfg.get('deny_ids', []):
        return 'existing_deny_id'
    if any(p.search(title) for p in collector.compile_deny(cfg).get(item.get('source'), ())):
        return 'existing_source_deny'
    if any(p.search(title) for p in collector.compile_allow(cfg).get(item.get('source'), ())):
        if not any(p.search(title) for p in rules['exclude']):
            return 'existing_source_allow'
    if item.get('tail_interview'):
        return 'preserve_tail_interview'
    if item.get('kind') in ('oncourt', 'ceremony'):
        return 'existing_inventory'
    kind = collector.classify(title, rules)
    if kind in ('oncourt', 'ceremony', 'excluded'):
        return 'existing_title_rule'
    return 'candidate'


class Ledger:
    """SQLite serializes budget reservation, cache writes, and same-key claim across workers."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, stamp REAL, response TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS claims (key TEXT PRIMARY KEY, stamp REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS budgets (day TEXT PRIMARY KEY, calls INTEGER)')
        self.db.commit()

    def reserve(self, key, *, live, daily_limit, now=None):
        now = time.time() if now is None else now
        day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date().isoformat()
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('DELETE FROM claims WHERE stamp < ?', (now-300,))
            cached = self.db.execute('SELECT stamp,response FROM cache WHERE key=?',(key,)).fetchone()
            if cached and 0 <= now-cached[0] < 86400:
                try:
                    data = demo.validate(json.loads(cached[1]))
                    if data['model'] != MODEL: raise ValueError('model mismatch')
                    self.db.commit()
                    return 'cache_hit', data
                except (ValueError, KeyError, TypeError, AttributeError):
                    self.db.execute('DELETE FROM cache WHERE key=?',(key,))
            if not live:
                self.db.commit(); return 'would_call', None
            if self.db.execute('SELECT 1 FROM claims WHERE key=?',(key,)).fetchone():
                self.db.commit(); return 'inflight_fallback', None
            calls = self.db.execute('SELECT calls FROM budgets WHERE day=?',(day,)).fetchone()
            if calls and calls[0] >= daily_limit:
                self.db.commit(); return 'daily_budget_fallback', None
            self.db.execute('INSERT INTO budgets VALUES (?,1) ON CONFLICT(day) DO UPDATE SET calls=calls+1',(day,))
            self.db.execute('INSERT INTO claims VALUES (?,?)',(key,now))
            self.db.commit(); return 'reserved', None
        except Exception:
            self.db.rollback(); raise

    def finish(self, key, response=None):
        if response is not None:
            demo.validate(response)
            if response['model'] != MODEL: raise ValueError('unexpected model')
            self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,time.time(),json.dumps(response)))
        self.db.execute('DELETE FROM claims WHERE key=?',(key,))
        self.db.commit()


def fingerprint(item):
    body = demo.build_request(item)
    body['model'] = MODEL
    return hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def run(items, cfg, ledger, *, live=False, max_calls=20, daily_limit=50, caller=None):
    rules=collector.compile_rules(cfg)
    counts=collections.Counter(); records=[]; seen=set(); attempted=0; failures=0; circuit=False; tokens=0
    caller=caller or (lambda item,key,live: demo.run_one(item,key,live,model=MODEL,timeout=8))
    for item in items:
        reason=plan(item,cfg,rules)
        row={'id':str(item.get('id','')), 'decision':reason,'production_action':'unchanged'}
        if reason=='candidate':
            try: key=fingerprint(item)
            except (ValueError,TypeError):
                row['decision']='invalid_input_fallback';records.append(row);counts[row['decision']]+=1;continue
            if key in seen:
                row['decision']='duplicate_in_batch'
            else:
                seen.add(key)
                # Cache is useful even when the network circuit/budget is exhausted.
                status,data=ledger.reserve(key,live=False,daily_limit=daily_limit)
                if status!='cache_hit':
                    if circuit: status='circuit_fallback'
                    elif live and attempted>=max_calls: status='run_budget_fallback'
                    elif live and not os.getenv('TYPESAFE_API_KEY'): status='missing_key_fallback'
                    else: status,data=ledger.reserve(key,live=live,daily_limit=daily_limit)
                row['decision']=status
                if status=='reserved':
                    attempted+=1
                    try:
                        result=caller(item,os.environ['TYPESAFE_API_KEY'],True)
                        if result['status']=='ok':
                            data=demo.validate(result['response'])
                            tokens+=data['usage']['input_tokens']
                            if data['model']!=MODEL: raise ValueError('model mismatch')
                            ledger.finish(key,data);row['decision']='api_ok';failures=0
                        else:
                            ledger.finish(key);row['decision']=result['status']+'_fallback';failures+=1
                            circuit=result.get('http_status') in (401,402,403,429) or failures>=3
                        row['elapsed_ms']=result.get('elapsed_ms')
                    except (ValueError,KeyError,TypeError,AttributeError):
                        ledger.finish(key);row['decision']='invalid_response_fallback';failures+=1;circuit=failures>=3;data=None
                if data is not None and row['decision'] in ('cache_hit','api_ok'):
                    a=data['answers']['column']
                    row.update(suggestion=a['choice'],confidence=a['confidence'],model=data['model'])
                    row['needs_review']=a['choice']=='uncertain' or a['confidence']<.9 or data['answers']['evidence']['choice']=='insufficient'
        records.append(row);counts[row['decision']]+=1
    return {'mode':'shadow','model':MODEL,'total':len(items),'counts':dict(counts),'api_attempts':attempted,
            'known_input_tokens':tokens,'estimated_known_jev_cost_usd':tokens*.042/1e6,
            'unconfirmed_billing_calls':attempted-counts.get('api_ok',0),
            'savings_vs_current_pipeline_usd':None,'production_dispatches':0,'records':records}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'data/oncourt_interviews.json')
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--live',action='store_true')
    p.add_argument('--max-calls',type=int,default=20)
    p.add_argument('--daily-limit',type=int,default=50)
    a=p.parse_args()
    if not 1<=a.max_calls<=50 or not 1<=a.daily_limit<=200:p.error('bounded call limits required')
    if a.output.exists() or a.output.resolve() in (a.input.resolve(),a.cache.resolve()):p.error('output must be new')
    os.environ['JEV_MODEL']=MODEL
    raw=json.loads(a.input.read_text());items=raw.get('items',raw)
    if isinstance(items,dict):items=[dict(v,id=k) for k,v in sorted(items.items())]
    if not isinstance(items,list) or any(not isinstance(i,dict) for i in items):p.error('invalid candidates')
    a.cache.parent.mkdir(parents=True,exist_ok=True)
    ledger=Ledger(a.cache)
    try: result=run(items,collector.load_sources(),ledger,live=a.live,max_calls=a.max_calls,daily_limit=a.daily_limit)
    finally: ledger.db.close()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
