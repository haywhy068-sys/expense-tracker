import {mockRequest} from './mock';
export const IS_MOCK=import.meta.env.DEV && import.meta.env.VITE_MOCK_API==='true';
import type {AuthResponse,Expense,ExpenseInput} from './types';
const BASE=(import.meta.env.VITE_API_URL||'/api').replace(/\/+$/,'');
const apiURL=(path:string)=>BASE.endsWith('/api')?BASE+path.slice(4):BASE+path;
let token:string|null=null;let onExpired=()=>{};
export function setSession(value:string|null,expired?:()=>void){token=value;if(expired)onExpired=expired;}
async function request<T>(path:string,options:RequestInit={},protectedRoute=true):Promise<T>{
 const headers=new Headers(options.headers);headers.set('Accept','application/json');if(options.body)headers.set('Content-Type','application/json');if(protectedRoute&&token)headers.set('Authorization',`Bearer ${token}`);
 if(IS_MOCK)return await mockRequest(path,{...options,headers}) as T;
 const r=await fetch(apiURL(path),{...options,headers});if(r.status===401&&protectedRoute){setSession(null);onExpired();throw Error('Your session expired. Please sign in again.');}
 const payload=await r.text();let data:any=null;try{data=payload?JSON.parse(payload):null;}catch{throw Error('The API returned a non-JSON response. Check the API URL and server.');}
 if(!r.ok)throw Error(data?.message||data?.error||`Request failed (${r.status}).`);return data as T;
}
export async function authenticate(mode:'login'|'register',email:string,password:string){const r=await request<AuthResponse>(`/api/auth/${mode}`,{method:'POST',body:JSON.stringify({email,password})},false);if(!r?.token||!r.user?.email||r.user.id===undefined)throw Error('The authentication response must include token and user.');return r;}
export async function listExpenses(filters:{category?:string;start_date?:string;end_date?:string},signal?:AbortSignal){const query=new URLSearchParams();for(const [k,v] of Object.entries(filters))if(v)query.set(k,v);const r=await request<Expense[]>(`/api/expenses?${query}`,{signal});if(!Array.isArray(r))throw Error('GET /api/expenses must return a JSON array.');for(const e of r){if(e.id===undefined||typeof e.date!=='string'||typeof e.category!=='string'||typeof e.description!=='string'||typeof e.amount!=='number'||!Number.isFinite(e.amount))throw Error('An expense response does not match the agreed contract.');}return r;}
export function createExpense(x:ExpenseInput){return request<Expense>('/api/expenses',{method:'POST',body:JSON.stringify(x)});}
export function updateExpense(id:Expense['id'],x:ExpenseInput){return request<Expense>('/api/expenses/'+encodeURIComponent(id),{method:'PUT',body:JSON.stringify(x)});}
export function deleteExpense(id:Expense['id']){return request<void>('/api/expenses/'+encodeURIComponent(id),{method:'DELETE'});}
