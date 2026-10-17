from pathlib import Path
import subprocess,json,textwrap
REPO='robertyang87/tennislive';BRANCH='codex/iga-qf-native-qc-recovery';BASE='ddc4f75e'
def api(route,payload=None):
 cmd=['gh','api','repos/'+REPO+'/'+route]
 if payload is not None:cmd+=['--method','POST','--input','-']
 p=subprocess.run(cmd,input=json.dumps(payload)if payload is not None else None,text=True,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr[-700:])
 return json.loads(p.stdout)
base=api('commits/'+BASE)['sha'];script=Path('/workspace/scratch/iga-qf-resume-native.py').read_text();compile(script,'resume','exec')
w='''name: Recover exact native Swiatek QF and run actual L2 QC
on:
  workflow_dispatch:
permissions:
  contents: write
  actions: read
jobs:
  recover:
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
        with:
          ref: BASE
          fetch-depth: 1
          sparse-checkout: |
            .github
            src
            tools
            specs
            assets
            data
            output/2026-10-16/reel/swiatek-li-wuhan-2026-qf
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install native read/QC dependencies only
        run: pip install -q -e . numpy pypinyin
      - name: Install actual native ffmpeg and ffprobe dependency
        run: |
          source tools/ci_apt_install.sh
          ensure_ffmpeg
          command -v ffprobe
      - name: Authenticate exact original artifact; native checks; Release transport
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          python - <<'PY_RECOVER'
SCRIPT
          PY_RECOVER
      - name: Preserve actual recovered native bytes and honest original provenance
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: recovered-native-input-swiatek-li-wuhan-2026-qf-${{ github.run_number }}
          path: /tmp/recovered-native-input
          compression-level: 0
          if-no-files-found: warn
          retention-days: 14
'''.replace('ref: BASE','ref: '+base).replace('SCRIPT',textwrap.indent(script,'          ').rstrip())
tree=api('git/commits/'+base)['tree']['sha'];t=api('git/trees',{'base_tree':tree,'tree':[{'path':'.github/workflows/frame-grab.yml','mode':'100644','type':'blob','content':w}]})['sha'];head=api('git/commits',{'message':'recovery: native QC of same authenticated Swiatek movie; no reencoding','tree':t,'parents':[base]})['sha'];api('git/refs',{'ref':'refs/heads/'+BRANCH,'sha':head});Path('/workspace/scratch/iga-qf-native-resume-dispatch.json').write_text(json.dumps({'branch':BRANCH,'head':head,'checked_out_code_head':base,'original_render_run':38912186473,'original_head':'a1785b14ec5b18029a20e47e655160888b54db4f','quality_approval':False},indent=2)+'\n');print(BRANCH,head,flush=True)
subprocess.run(['gh','workflow','run','frame-grab.yml','--ref',BRANCH],check=True)
