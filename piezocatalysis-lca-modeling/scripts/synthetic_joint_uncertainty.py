#!/usr/bin/env python3
"""Demonstrate seeded sampling of a finite, explicitly paired synthetic joint distribution."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys


def run(data):
    if not isinstance(data, dict) or data.get('purpose') != 'synthetic_validation_only':
        raise ValueError('purpose must be synthetic_validation_only')
    if not isinstance(data.get('source'),str) or not data['source'].strip(): raise ValueError('source required')
    seed, n = data.get('seed'), data.get('iterations')
    if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError('seed must be an integer')
    if isinstance(n,bool) or not isinstance(n,int) or not 2<=n<=1000000: raise ValueError('iterations must be 2 to 1000000')
    states=data.get('joint_states')
    if not isinstance(states,list) or len(states)<2: raise ValueError('at least two joint states are required')
    names=set(); probs=[]; values=[]; input_keys=None
    for s in states:
        if not isinstance(s,dict) or not isinstance(s.get('id'),str) or not s['id'] or s['id'] in names:
            raise ValueError('state IDs must be unique and nonempty')
        names.add(s['id'])
        for k in ('probability','response'):
            v=s.get(k)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError(f'{k} must be finite')
        if s['probability']<0: raise ValueError('probability must not be negative')
        if not isinstance(s.get('paired_inputs'),dict) or not s['paired_inputs']: raise ValueError('paired_inputs must document the joint state')
        inputs=s['paired_inputs']
        if any(not isinstance(k,str) or not k.strip() or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for k,v in inputs.items()):
            raise ValueError('paired_inputs must contain named finite numeric values')
        if input_keys is None: input_keys=set(inputs)
        elif set(inputs)!=input_keys: raise ValueError('all joint states must specify the same paired inputs')
        probs.append(s['probability']);values.append(s['response'])
    if not math.isclose(math.fsum(probs),1,rel_tol=1e-12,abs_tol=1e-12): raise ValueError('probabilities must sum to 1')
    mean=math.fsum(p*v for p,v in zip(probs,values))
    variance=math.fsum(p*(v-mean)**2 for p,v in zip(probs,values))
    rng=random.Random(seed); samples=[]; counts=[0]*len(states)
    for _ in range(n):
        draw=rng.random();cumulative=0.0;idx=len(states)-1
        for i,prob in enumerate(probs):
            cumulative+=prob
            if draw<cumulative: idx=i;break
        counts[idx]+=1;samples.append(values[idx])
    ordered=sorted(samples)
    stderr=math.sqrt(variance/n)
    checkpoints=sorted({max(1,n//4),max(1,n//2),n})
    convergence=[{'iterations':k,'sample_mean':statistics.fmean(samples[:k]),
                  'analytical_standard_error':math.sqrt(variance/k)} for k in checkpoints]
    def quantile(p):
        x=(n-1)*p;lo=math.floor(x);hi=math.ceil(x)
        return ordered[lo]+(ordered[hi]-ordered[lo])*(x-lo)
    return {'purpose':data['purpose'],'source':data['source'],'seed':seed,'iterations':n,
            'random_generator':'Python random.Random; record Python version for reproduction',
            'analytical_mean':mean,'analytical_population_standard_deviation':math.sqrt(variance),
            'sample_mean':statistics.fmean(samples),'sample_standard_deviation':statistics.stdev(samples),
            'analytical_standard_error_of_mean':stderr,
            'mean_error_in_analytical_standard_errors':(statistics.fmean(samples)-mean)/stderr if stderr else None,
            'prefix_convergence_diagnostics':convergence,
            'prefix_half_mean':statistics.fmean(samples[:n//2]),
            'quantile_method':'linear interpolation at (n-1)*p',
            'sample_quantiles':{'0.025':quantile(.025),'0.5':quantile(.5),'0.975':quantile(.975)},
            'state_counts':{s['id']:counts[i] for i,s in enumerate(states)},
            'note':'Synthetic joint states are sampled together; Prefix means and analytical standard errors diagnose this finite synthetic model only, not proof of convergence. Model quantiles are not experimental confidence intervals.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);a=p.parse_args()
    try:
        raw=a.input.read_bytes();data=json.loads(raw);r=run(data);r['input_sha256']=hashlib.sha256(raw).hexdigest();r['python_version']=sys.version.split()[0]
        print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,OverflowError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
