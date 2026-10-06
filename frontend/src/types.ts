export type User={id:string|number;email:string};
export type Expense={id:string|number;date:string;category:string;description:string;amount:number};
export type ExpenseInput=Omit<Expense,'id'>;
export type AuthResponse={token:string;user:User};
