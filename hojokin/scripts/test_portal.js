// ポータルの逆引き・重層・フィルタの回帰テスト（本番HTMLの埋め込みJSを無改変で実行）。
// 使い方: node scripts/test_portal.js
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'kaigo-hojokin-portal.html'), 'utf-8');
const prod = html.match(/<script>([\s\S]*)<\/script>/)[1];

// DOMスタブ
const elems = {};
function __el(){ return {innerHTML:'',textContent:'',value:'deadline',checked:true,style:{},
  classList:{toggle(){},add(){},remove(){}},dataset:{}}; }
global.document = {getElementById:(id)=>elems[id]||(elems[id]=__el()), querySelectorAll:()=>[], body:{dataset:{}}};
global.window = {}; global.alert = ()=>{};

const tests = `
function setState(pref,equips,status,levels){state.pref=pref||'';state.equips=new Set(equips||[]);state.status=new Set(status||[]);state.levels=new Set(levels||['国','都道府県','市区町村']);state.q='';}
function ids(){return SEIDO.map(evaluate).filter(Boolean).map(e=>e.rec.id);}
const T=[];
setState('',['ROB-09'],['受付中']); let r1=ids();
T.push(['T1 見守り(ROB-09)×受付中で沖縄包含(偽陰性の回帰)', r1.includes('P-47'), r1.length+'件']);
setState('',['FUK-01'],[]); let r2=ids();
T.push(['T2 FUK-01(天井リフト)はG-01のみ', JSON.stringify(r2)==='["G-01"]', r2.join(',')]);
setState('東京都',['ROB-09'],[]); let r3=ids();
T.push(['T3 東京×見守り=都+港区+葛飾', r3.sort().join(',')==='M-01,M-05,P-13', r3.join(',')]);
setState('埼玉県',['ICT-05'],[]); let r4=ids();
T.push(['T4 埼玉×インカム=国+県+さいたま市', r4.sort().join(',')==='G-01,M-03,P-11', r4.join(',')]);
setState('',['ICT-04'],[]); let r5=ids();
T.push(['T5 タブレット(ICT-04)でG-01(非対象)除外', !r5.includes('G-01'), r5.length+'件']);
setState('',[],[],['市区町村']); let r6=ids();
T.push(['T6 実施主体=市区町村のみ→14件', r6.length===14, r6.length+'件']);
state.q='千葉'; state.equips=new Set(['ROB-09']); state.status=new Set(); state.pref=''; state.levels=new Set(['国','都道府県','市区町村']);
let r7=ids();
T.push(['T7 検索"千葉"×ROB-09=県+千葉市', r7.sort().join(',')==='M-08,P-12', r7.join(',')]);
setState('神奈川県',[],[]); let r8=ids();
T.push(['T8 神奈川の重層束ね(国2+県+市3)', r8.sort().join(',')==='G-01,G-02,M-07,M-10,M-12,P-14', r8.join(',')]);
setState('千葉県',['ROB-09'],[]); let r9=ids();
T.push(['T9 機器タグ空(柏M-13)は機器選択で除外', !r9.includes('M-13'), r9.join(',')]);
setState('',[],[]); let r10=ids();
T.push(['T10 無条件=全件表示', r10.length===SEIDO.length, r10.length+'件']);
let pass=0, fail=0;
for(const t of T){ const ok=t[1]===true; if(ok)pass++; else fail++; console.log((ok?'✅':'❌')+' '+t[0]+' | '+t[2]); }
console.log('\\n結果: '+pass+' PASS / '+fail+' FAIL  (SEIDO '+SEIDO.length+'件)');
if(fail) process.exitCode=1;
`;

eval(prod + '\n' + tests);
