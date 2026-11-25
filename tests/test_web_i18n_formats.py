"""Localized statistics, dates, and known API errors preserve raw data."""

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_localized_statistics_and_dates(tmp_path):
    node = shutil.which("node")
    assert node is not None
    shutil.copytree(STATIC / "js", tmp_path / "js")
    shutil.copytree(STATIC / "locales", tmp_path / "locales")
    (tmp_path / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    script = r"""
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const base = pathToFileURL(process.argv[1] + '/');
const {createI18n} = await import(new URL('js/i18n.js', base));
const {createDynamicPresentation} = await import(new URL('js/i18n-presentation.js', base));
const {createPublicStatsController} = await import(new URL('js/public-stats.js', base));
const {createDashboardController} = await import(new URL('js/dashboard.js', base));
const {createStationRenderer} = await import(new URL('js/station-renderer.js', base));
const {knownApiErrorKey} = await import(new URL('js/api.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const date = '2026-11-24T12:00:00Z';
const dateNode = {textContent:'Last played: original',dataset:{stationLastPlayed:date}};
const rawNode = {textContent:'Play'};
// Model the leaf nodes emitted by the trusted renderer. No HTML parser is assumed.
function container(){
  let markup='', nodes=[], writes=0;
  const result = {addEventListener(){}, get innerHTML(){return markup;},
    set innerHTML(value){markup=value;writes++;nodes=[];
      for (const match of value.matchAll(/<([a-z0-9]+)\b([^<>]*data-render-[^<>]*)>([^<>]*)<\/\1>/g)) {
        const dataset={};
        for (const attr of match[2].matchAll(/data-render-([a-z0-9-]+)(?:="([^"]*)")?/g)) {
          const key='render'+attr[1].replace(/(^|-)([a-z])/g,(_,a,b)=>b.toUpperCase());
          dataset[key]=attr[2]??'';
        }
        nodes.push({dataset,textContent:match[3]});
      }
    },
    querySelectorAll(selector){if(selector==='*')return nodes;
      const keys={'[data-render-i18n]':'renderI18n','[data-render-number]':'renderNumber',
        '[data-render-aria]':'renderAria'};
      return nodes.filter(n=>keys[selector] in n.dataset);},
    get writes(){return writes;}};
  return result;
}
const publicNode=container(), metrics=container(), message={textContent:''};
const root={querySelectorAll:()=>[...publicNode.querySelectorAll('*'),...metrics.querySelectorAll('*'),message,dateNode,rawNode]};
let calls=0;
const payload={totals:{plays:1234567,users:2},top_stations:[{name:'<img>Play',play_count:1234567}]};
const publicStats=createPublicStatsController({presentation,contentNode:publicNode,messageNode:message,
  fetchImpl:async url=>{calls++;return {ok:true,json:async()=>url.endsWith('/stats')?payload:{}};}});
await i18n.setLocale('en'); presentation.refresh(root,i18n);
await publicStats.loadPublicStats();
assert.equal(calls,4);
assert.match(publicNode.innerHTML,/&lt;img&gt;Play/);
const metricController=createDashboardController({presentation,userMetricsNode:metrics});
metricController.renderDashboard({user:{favorites_count:1234567}});
const find=(parent,key)=>parent.querySelectorAll('[data-render-i18n]').find(n=>n.dataset.renderI18n===key);
const count=find(publicNode,'public.play_count'), favorite=find(metrics,'nav.favorites');
const number=metrics.querySelectorAll('[data-render-number]')[0];
assert.equal(count.textContent,'1,234,567 plays');
assert.equal(favorite.textContent,'Favorites');
assert.equal(number.textContent,'1,234,567');
globalThis.document={querySelectorAll:s=>s==='[data-station-last-played]'?[dateNode]:[]};
const renderer=createStationRenderer({presentation});
assert.match(renderer.renderStation({name:'Play',last_played_at:date}),/data-station-last-played="2026-11-24T12:00:00Z"/);
renderer.bindResultActions();
const originalDate=dateNode.textContent;
await i18n.setLocale('fr'); presentation.refresh(root,i18n);
assert.equal(count.textContent,new Intl.NumberFormat('fr').format(1234567)+' écoutes');
assert.equal(number.textContent,new Intl.NumberFormat('fr').format(1234567));
assert.equal(favorite.textContent,i18n.t('nav.favorites'));
assert.equal(dateNode.textContent,i18n.t('station.last_played',{date:new Date(date).toLocaleString('fr')}));
assert.notEqual(dateNode.textContent,originalDate);
assert.equal(publicNode.writes,1); assert.equal(metrics.writes,1); assert.equal(calls,4);
assert.equal(payload.top_stations[0].name,'<img>Play'); assert.equal(rawNode.textContent,'Play');
assert.equal(knownApiErrorKey('Invalid username or password.'),'api.invalid_credentials');
assert.equal(knownApiErrorKey('Invalid username or password. extra'),undefined);
assert.equal(knownApiErrorKey('__proto__'),undefined);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
