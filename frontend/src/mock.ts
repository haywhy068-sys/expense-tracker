import type {Expense} from './types';
// Browser-memory fixtures only. This module never contacts a backend.
const now=new Date();const month=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
let nextId=7;
let records:Expense[]=[
 {id:1,date:month+'-05',category:'Food',description:'Weekly grocery shopping',amount:12050},
 {id:2,date:month+'-04',category:'Transport',description:'Taxi to the office',amount:4500},
 {id:3,date:month+'-03',category:'Utilities',description:'Internet subscription',amount:22000},
 {id:4,date:month+'-02',category:'Food',description:'Lunch with colleagues',amount:6500},
 {id:5,date:month+'-01',category:'Shopping',description:'Office supplies',amount:8750},
 {id:6,date:month+'-04',category:'Health',description:'Pharmacy essentials',amount:3800}
];
export async function mockRequest(path:string,options:RequestInit={}):Promise<unknown>{
 if(options.signal?.aborted)throw new DOMException('Aborted','AbortError');
 const url=new URL(path,'https://mock.invalid');const method=options.method||'GET';
 const body=options.body?JSON.parse(String(options.body)):null;
 if(url.pathname==='/api/auth/login'||url.pathname==='/api/auth/register'){
  if(!body?.email||!body?.password)throw Error('Enter sample email and password values.');
  return {token:'mock-session-only',user:{id:'sample-user',email:String(body.email)}};
 }
 if(new Headers(options.headers).get('Authorization')!=='Bearer mock-session-only')throw Error('Open the sample dashboard first.');
 if(url.pathname==='/api/expenses'&&method==='GET'){
  const category=url.searchParams.get('category'),start=url.searchParams.get('start_date'),end=url.searchParams.get('end_date');
  return structuredClone(records.filter(e=>(!category||category==='All'||e.category===category)&&(!start||e.date>=start)&&(!end||e.date<=end)).sort((a,b)=>b.date.localeCompare(a.date)||Number(b.id)-Number(a.id)));
 }
 if(method==='POST'&&url.pathname==='/api/expenses'){const created={id:nextId++,...body};records.push(created);return structuredClone(created);}
 const id=decodeURIComponent(url.pathname.split('/').pop()||'');const index=records.findIndex(e=>String(e.id)===id);
 if(index<0)throw Error('This sample expense was not found.');
 if(method==='PUT'){records[index]={id:records[index].id,...body};return structuredClone(records[index]);}
 if(method==='DELETE'){records.splice(index,1);return null;}
 throw Error('This route is not available in mock mode.');
}
