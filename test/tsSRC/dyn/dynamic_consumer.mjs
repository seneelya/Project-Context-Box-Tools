const target = await import('./target');
target.widget();

const { GADGET } = await import('./target');
console.log(GADGET);
