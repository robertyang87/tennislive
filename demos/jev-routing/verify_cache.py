"""Run the explicitly selected sample once, then verify a warm run cannot open the network."""
import argparse
import datetime
import json
from pathlib import Path
import time
from unittest.mock import patch

import selective


def main():
    here=Path(__file__).parent
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout',type=int,choices=(8,30),default=8)
    parser.add_argument('--output-name',choices=('cache-verification','cache-verification-diagnostic'),default='cache-verification')
    args=parser.parse_args()
    out=here/args.output_name
    out.mkdir(exist_ok=False)
    samples=json.loads((here/'new-item-replay.json').read_text())['items']
    assert len(samples)==1 and samples[0]['title']=='Shapovalov reacts to winning his first ATP 500!'
    ledger=selective.Ledger('/tmp/jev-authorized-cache-verification.sqlite')
    receipts=[]
    def caller(item,key,live):
        r=selective.demo.run_one(item,key,live,model=selective.MODEL,timeout=args.timeout)
        receipts.append(r)
        return r
    try:
        start=time.monotonic()
        cold=selective.run(samples,selective.collector.load_sources(),ledger,live=True,max_calls=1,daily_limit=4,caller=caller)
        cold['wall_ms']=round((time.monotonic()-start)*1000,3)
        (out/'cold.json').write_text(json.dumps(cold,ensure_ascii=False,indent=2))
        (out/'api-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
        if cold['counts']!={'api_ok':1}:
            print(json.dumps({'cold':cold,'warm':'not_attempted'},ensure_ascii=False));return 2
        start=time.monotonic()
        # Reopen the database: this tests persistence across runs, not a process-local dictionary.
        ledger.db.close();ledger=selective.Ledger('/tmp/jev-authorized-cache-verification.sqlite')
        with patch.object(selective.demo.urllib.request,'build_opener',side_effect=AssertionError('warm run must not access network')) as network:
            warm=selective.run(samples,selective.collector.load_sources(),ledger,live=True,max_calls=1,daily_limit=4)
            network.assert_not_called()
        warm['wall_ms']=round((time.monotonic()-start)*1000,3)
        assert warm['counts']=={'cache_hit':1} and warm['api_attempts']==0
        for field in ('suggestion','confidence','model','needs_review'):
            assert cold['records'][0][field]==warm['records'][0][field]
        (out/'warm.json').write_text(json.dumps(warm,ensure_ascii=False,indent=2))
        summary={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'sample_count':1,'diagnostic_socket_timeout_s':args.timeout,'cold_api_attempts':cold['api_attempts'],'warm_api_attempts':warm['api_attempts'],
                 'cold_wall_ms':cold['wall_ms'],'warm_wall_ms':warm['wall_ms'],
                 'input_tokens':cold['known_input_tokens'],'estimated_known_cost_usd':cold['estimated_known_jev_cost_usd'],
                 'network_disabled_during_warm_verification':True,'cache_survived_database_reopen':True,
                 'classification':cold['records'][0],'production_dispatches':0}
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        print(json.dumps(summary,ensure_ascii=False));return 0
    finally:ledger.db.close()

if __name__=='__main__':raise SystemExit(main())
