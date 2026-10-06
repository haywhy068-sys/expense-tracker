export const cents = n => Math.round((Number(n) + Number.EPSILON) * 100);
export const totalCents = rows => rows.reduce((sum,e)=>sum+cents(e.amount),0);
export function csv(rows){const cell=value=>{let s=String(value);if(/^[\s]*[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};return '\uFEFF'+[['id','date','category','description','amount'],...rows.map(e=>[e.id,e.date,e.category,e.description,Number(e.amount).toFixed(2)])].map(row=>row.map(cell).join(',')).join('\r\n');}
