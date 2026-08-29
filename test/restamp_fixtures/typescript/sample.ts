export function isOurTool(name: string) {
  return name === 'x';
}

export async function loadIt(x: string) {
  return x;
}

export const ALLOWED_TOOLS = ['read_file', 'write_file'];

export const BRAND_NEW_CONST = 42;
