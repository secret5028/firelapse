"""Prepare a frozen ON/OFF comparison; execute only with explicit --run."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.diagnostics import prepare_bulk_pair,run_bulk_pair

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--engine',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--timeout',type=float,default=600.)
    args=parser.parse_args()
    if args.source:
        if not args.engine:parser.error('--engine is required when preparing')
        result=prepare_bulk_pair(args.source,args.output,args.engine)
    elif not args.run:parser.error('--source or --run is required')
    if args.run:result=run_bulk_pair(args.output,args.timeout)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
